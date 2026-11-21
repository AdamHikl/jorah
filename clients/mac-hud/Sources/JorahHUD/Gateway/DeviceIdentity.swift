import CryptoKit
import Foundation

/// The HUD's Ed25519 device identity. The encodings match OpenClaw 2026.10.9
/// (`apps/shared/OpenClawKit/.../DeviceIdentity.swift` and
/// `packages/gateway-client/src/device-auth.ts`):
/// - device id: lowercase hex SHA-256 of the raw 32-byte public key
/// - public key and signature on the wire: base64url without padding
/// - signed payload: the `v3` pipe-joined string
struct DeviceIdentity {
    let privateKey: Curve25519.Signing.PrivateKey

    static let keyAccount = "device-key"

    /// Loads the key from the Keychain, or creates and stores one.
    /// Returns nil if the key cannot be stored, so the HUD never pairs an identity it would lose.
    static func loadOrCreate() -> DeviceIdentity? {
        if let raw = Keychain.read(keyAccount),
           let key = try? Curve25519.Signing.PrivateKey(rawRepresentation: raw) {
            return DeviceIdentity(privateKey: key)
        }
        let key = Curve25519.Signing.PrivateKey()
        guard Keychain.write(keyAccount, key.rawRepresentation) else { return nil }
        return DeviceIdentity(privateKey: key)
    }

    var publicKeyData: Data { privateKey.publicKey.rawRepresentation }

    var deviceId: String {
        SHA256.hash(data: publicKeyData).map { String(format: "%02x", $0) }.joined()
    }

    var publicKeyBase64Url: String { Self.base64Url(publicKeyData) }

    func sign(_ payload: String) -> String? {
        guard let signature = try? privateKey.signature(for: Data(payload.utf8)) else { return nil }
        return Self.base64Url(signature)
    }

    static func base64Url(_ data: Data) -> String {
        data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }

    /// `buildDeviceAuthPayloadV3`: the Gateway compares this byte for byte.
    static func authPayloadV3(
        deviceId: String,
        clientId: String,
        clientMode: String,
        role: String,
        scopes: [String],
        signedAtMs: Int64,
        token: String?,
        nonce: String,
        platform: String?,
        deviceFamily: String?
    ) -> String {
        [
            "v3",
            deviceId,
            clientId,
            clientMode,
            role,
            scopes.joined(separator: ","),
            String(signedAtMs),
            token ?? "",
            nonce,
            normalizeMetadata(platform),
            normalizeMetadata(deviceFamily),
        ].joined(separator: "|")
    }

    /// `normalizeDeviceMetadataForAuth`: trim, then lowercase ASCII letters only.
    static func normalizeMetadata(_ value: String?) -> String {
        guard let value else { return "" }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return String(trimmed.unicodeScalars.map { scalar -> Character in
            if scalar.value >= 65, scalar.value <= 90, let lower = Unicode.Scalar(scalar.value + 32) {
                return Character(lower)
            }
            return Character(scalar)
        })
    }
}
