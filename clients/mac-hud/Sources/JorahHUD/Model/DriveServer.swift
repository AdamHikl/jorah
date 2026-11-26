import Darwin
import Foundation
import HUDCore

/// The drive socket (ADR 0012). It exists only while Adam has drive mode armed: `start` creates
/// it, `stop` removes it. It lives in a folder only Adam's user can open, the socket itself is
/// mode 600, and a connection from another user id is closed unread. One request per connection:
/// a JSON line in, a JSON line out.
final class DriveServer: @unchecked Sendable {
    typealias Handler = @MainActor (DriveCommand) async -> [String: Any]

    struct StartError: Error, CustomStringConvertible {
        let description: String
    }

    static var directory: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        return base.appendingPathComponent(HUDProfile.name.map { "JorahHUD-\($0)" } ?? "JorahHUD", isDirectory: true)
    }

    static var socketPath: String { directory.appendingPathComponent("drive.sock").path }
    static var logPath: String { directory.appendingPathComponent("drive.log").path }

    private let handler: Handler
    private let queue = DispatchQueue(label: "dev.jorah.hud.drive")
    private var source: DispatchSourceRead?
    private var path: String?

    init(handler: @escaping Handler) {
        self.handler = handler
    }

    func start() throws {
        let directory = Self.directory
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true,
                                                attributes: [.posixPermissions: 0o700])
        guard chmod(directory.path, 0o700) == 0 else { throw StartError(description: "can't make \(directory.path) private") }

        let path = Self.socketPath
        var info = stat()
        if lstat(path, &info) == 0 {
            // A socket left by a HUD that didn't quit cleanly. Anything else there is not ours.
            guard (info.st_mode & S_IFMT) == S_IFSOCK, info.st_uid == getuid() else {
                throw StartError(description: "\(path) exists and is not the HUD's socket")
            }
            unlink(path)
        }

        let fd = socket(AF_UNIX, SOCK_STREAM, 0)
        guard fd >= 0 else { throw StartError(description: "no socket: \(String(cString: strerror(errno)))") }
        _ = fcntl(fd, F_SETFD, FD_CLOEXEC)

        var address = sockaddr_un()
        address.sun_family = sa_family_t(AF_UNIX)
        let bytes = Array(path.utf8)
        let capacity = MemoryLayout.size(ofValue: address.sun_path)
        guard bytes.count < capacity else {
            close(fd)
            throw StartError(description: "the socket path is too long")
        }
        withUnsafeMutableBytes(of: &address.sun_path) { buffer in
            buffer.copyBytes(from: bytes)
            buffer[bytes.count] = 0
        }
        address.sun_len = UInt8(MemoryLayout<sockaddr_un>.size)
        let bound = withUnsafePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(fd, $0, socklen_t(MemoryLayout<sockaddr_un>.size)) }
        }
        guard bound == 0 else {
            let reason = String(cString: strerror(errno))
            close(fd)
            throw StartError(description: "can't bind \(path): \(reason)")
        }
        guard chmod(path, 0o600) == 0, listen(fd, 4) == 0 else {
            let reason = String(cString: strerror(errno))
            close(fd)
            unlink(path)
            throw StartError(description: "can't listen on \(path): \(reason)")
        }
        _ = fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK)

        let source = DispatchSource.makeReadSource(fileDescriptor: fd, queue: queue)
        source.setEventHandler { [weak self] in self?.acceptPending(fd) }
        source.setCancelHandler { close(fd) }
        source.resume()
        self.source = source
        self.path = path
    }

    func stop() {
        source?.cancel()
        source = nil
        if let path {
            unlink(path)
            self.path = nil
        }
    }

    deinit { stop() }

    private func acceptPending(_ listener: Int32) {
        while true {
            let client = accept(listener, nil, nil)
            guard client >= 0 else { return }
            var uid: uid_t = 0
            var gid: gid_t = 0
            guard getpeereid(client, &uid, &gid) == 0, uid == getuid() else {
                close(client)
                continue
            }
            _ = fcntl(client, F_SETFL, fcntl(client, F_GETFL) & ~O_NONBLOCK)
            var on: Int32 = 1
            setsockopt(client, SOL_SOCKET, SO_NOSIGPIPE, &on, socklen_t(MemoryLayout<Int32>.size))
            var timeout = timeval(tv_sec: 5, tv_usec: 0)
            setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout<timeval>.size))
            setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, &timeout, socklen_t(MemoryLayout<timeval>.size))
            DispatchQueue.global(qos: .userInitiated).async { [weak self] in self?.serve(client) }
        }
    }

    private func serve(_ client: Int32) {
        let request = Self.readLine(client)
        let handler = self.handler
        Task { @MainActor in
            let reply: [String: Any]
            switch DriveRequest.parse(request) {
            case .success(let command): reply = await handler(command)
            case .failure(let refusal): reply = ["ok": false, "error": refusal.message]
            }
            var data = (try? JSONSerialization.data(withJSONObject: reply, options: [.sortedKeys]))
                ?? Data(#"{"ok":false,"error":"The HUD couldn't write its answer."}"#.utf8)
            data.append(0x0A)
            DispatchQueue.global(qos: .userInitiated).async {
                Self.writeAll(client, data)
                close(client)
            }
        }
    }

    private static func readLine(_ fd: Int32) -> Data {
        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 4096)
        while data.count <= DriveRules.maxRequestBytes {
            let n = read(fd, &buffer, buffer.count)
            guard n > 0 else { break }
            data.append(contentsOf: buffer[0..<n])
            if let newline = data.firstIndex(of: 0x0A) { return data[data.startIndex..<newline] }
        }
        return data
    }

    private static func writeAll(_ fd: Int32, _ data: Data) {
        data.withUnsafeBytes { raw in
            guard var pointer = raw.baseAddress else { return }
            var left = raw.count
            while left > 0 {
                let n = write(fd, pointer, left)
                guard n > 0 else { return }
                pointer += n
                left -= n
            }
        }
    }
}
