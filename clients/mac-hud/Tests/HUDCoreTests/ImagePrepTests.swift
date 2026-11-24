import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
import XCTest
@testable import HUDCore

final class ImagePrepTests: XCTestCase {
    /// An image drawn in memory: a flat colour, or random noise (which compresses badly).
    private func image(width: Int, height: Int, alpha: Bool = false, noise: Bool = false) -> CGImage {
        let info = alpha ? CGImageAlphaInfo.premultipliedLast.rawValue : CGImageAlphaInfo.noneSkipLast.rawValue
        let context = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: width * 4,
                                space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: info)!
        if noise {
            let pixels = context.data!.assumingMemoryBound(to: UInt32.self)
            var seed: UInt32 = 12345
            for i in 0..<(width * height) {
                seed = seed &* 1_664_525 &+ 1_013_904_223
                pixels[i] = seed | (alpha ? 0 : 0xFF00_0000)
            }
        } else {
            context.setFillColor(CGColor(red: 0.2, green: 0.5, blue: 0.8, alpha: alpha ? 0.5 : 1))
            context.fill(CGRect(x: 0, y: 0, width: width, height: height))
        }
        return context.makeImage()!
    }

    private func encoded(_ image: CGImage, as type: UTType) -> Data {
        let out = NSMutableData()
        let dest = CGImageDestinationCreateWithData(out, type.identifier as CFString, 1, nil)!
        CGImageDestinationAddImage(dest, image, nil)
        XCTAssertTrue(CGImageDestinationFinalize(dest))
        return out as Data
    }

    func testASmallPNGIsSentAsItIs() throws {
        let data = encoded(image(width: 800, height: 600), as: .png)
        let prepared = try ImagePrep.prepare(data, fileName: "Screenshot 2026-11-23 at 10.15.02.png")
        XCTAssertEqual(prepared.data, data)
        XCTAssertEqual(prepared.mimeType, "image/png")
        XCTAssertEqual(prepared.fileName, "Screenshot-2026-11-23-at-10.15.02.png")
        XCTAssertEqual(prepared.width, 800)
        XCTAssertEqual(prepared.height, 600)
    }

    func testALargePhotoShrinksTo2048OnItsLongestSide() throws {
        let data = encoded(image(width: 4032, height: 3024), as: .jpeg)
        let prepared = try ImagePrep.prepare(data, fileName: "IMG_0042.JPG")
        XCTAssertEqual(prepared.mimeType, "image/jpeg")
        XCTAssertEqual(max(prepared.width, prepared.height), 2048)
        XCTAssertEqual(prepared.width, 2048)
        XCTAssertEqual(prepared.fileName, "IMG_0042.jpg")
        XCTAssertLessThanOrEqual(prepared.sizeBytes, ImagePrep.maxBytesPerImage)
    }

    func testTIFFIsRedrawnAndTransparencyStaysPNG() throws {
        let opaque = try ImagePrep.prepare(encoded(image(width: 300, height: 200), as: .tiff), fileName: nil)
        XCTAssertEqual(opaque.mimeType, "image/jpeg")
        XCTAssertEqual(opaque.fileName, "pasted-image.jpg")
        let clear = try ImagePrep.prepare(encoded(image(width: 300, height: 200, alpha: true), as: .tiff), fileName: "clip.tiff")
        XCTAssertEqual(clear.mimeType, "image/png")
        XCTAssertEqual(clear.fileName, "clip.png")
        XCTAssertEqual(clear.width, 300)
    }

    func testNoiseOverTheByteLimitEndsUnderIt() throws {
        let data = encoded(image(width: 2000, height: 2000, alpha: true, noise: true), as: .png)
        XCTAssertGreaterThan(data.count, ImagePrep.maxBytesPerImage)
        let prepared = try ImagePrep.prepare(data, fileName: "noise.png")
        XCTAssertLessThanOrEqual(prepared.sizeBytes, ImagePrep.maxBytesPerImage)
        XCTAssertTrue(["image/png", "image/jpeg"].contains(prepared.mimeType))
    }

    func testASmallShareShrinksAPictureThatWouldOtherwiseGoAsItIs() throws {
        let data = encoded(image(width: 1800, height: 1200, noise: true), as: .jpeg)
        XCTAssertGreaterThan(data.count, 300_000)
        let prepared = try ImagePrep.prepare(data, fileName: "photo.jpg", maxBytes: 300_000)
        XCTAssertLessThanOrEqual(prepared.sizeBytes, 300_000)
        XCTAssertEqual(prepared.mimeType, "image/jpeg")
    }

    func testTwentyPicturesShareTheMessageBudget() {
        // Twenty at once: each gets an equal share, under the per-picture cap.
        let each = ImagePrep.share(count: 20, usedBytes: 0)!
        XCTAssertEqual(each, ImagePrep.messageBudgetBytes / 20)
        XCTAssertLessThanOrEqual(each * 20, ImagePrep.messageBudgetBytes)
        // One alone gets at most the per-picture cap (the Gateway's 2 MB inline limit).
        XCTAssertEqual(ImagePrep.share(count: 1, usedBytes: 0), ImagePrep.maxBytesPerImage)
        // What's left is shared; a full message has no room.
        XCTAssertEqual(ImagePrep.share(count: 2, usedBytes: ImagePrep.messageBudgetBytes - 1_000_000), 500_000)
        XCTAssertNil(ImagePrep.share(count: 1, usedBytes: ImagePrep.messageBudgetBytes - 50_000))
        XCTAssertNil(ImagePrep.share(count: 0, usedBytes: 0))
        // The budget fits the Gateway's frame: 25 MiB of base64 minus room for the rest of the message.
        XCTAssertLessThan(ImagePrep.messageBudgetBytes * 4 / 3, 26_214_400 - 512 * 1024)
        XCTAssertEqual(ImagePrep.maxImagesPerMessage, 20)
    }

    func testNotAnImage() {
        XCTAssertThrowsError(try ImagePrep.prepare(Data("hello".utf8), fileName: "notes.txt")) { error in
            XCTAssertEqual(error as? ImagePrepError, .notAnImage)
        }
        XCTAssertThrowsError(try ImagePrep.prepare(Data(), fileName: nil))
    }

    func testFileNames() {
        XCTAssertEqual(ImagePrep.baseName(nil), "pasted-image")
        XCTAssertEqual(ImagePrep.baseName("../../etc/passwd"), "passwd")
        XCTAssertEqual(ImagePrep.baseName("Účtenka z Billa.heic"), "Uctenka-z-Billa")
        XCTAssertEqual(ImagePrep.baseName("..."), "pasted-image")
        XCTAssertEqual(ImagePrep.baseName(String(repeating: "a", count: 100) + ".png").count, 60)
    }

    func testHistoryMarkers() {
        let text = "what is this?\n[media attached: media://inbound/abc123]\n[media attached: media://inbound/def]"
        let stripped = HistoryPictures.strippingMarkers(text)
        XCTAssertEqual(stripped.text, "what is this?")
        XCTAssertEqual(stripped.count, 2)
        XCTAssertEqual(HistoryPictures.strippingMarkers("plain").count, 0)
        XCTAssertEqual(HistoryPictures.label(1), "🖼 1 picture")
        XCTAssertEqual(HistoryPictures.label(3), "🖼 3 pictures")
        XCTAssertEqual(HistoryPictures.withoutLabel("🖼 2 pictures\nsave these"), "save these")
        XCTAssertEqual(HistoryPictures.withoutLabel("🖼 1 picture"), "")
        XCTAssertEqual(HistoryPictures.withoutLabel("🖼 not a label\nx"), "🖼 not a label\nx")
    }
}
