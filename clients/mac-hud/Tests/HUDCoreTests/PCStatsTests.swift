import Foundation
import XCTest
@testable import HUDCore

final class PCStatsTests: XCTestCase {
    /// A real reading from the PC on 2026-11-21 (scripts/pc/pcstats.ps1 -Once), Core Temp not running.
    private let reading = """
    {"schema":"jorah-pcstats/1","at":"2026-11-21T14:16:43.492Z",
     "cpu":{"name":"Intel(R) Core(TM) i7-14700K","percent":5,"temperatureC":null,"temperatureSource":null},
     "memory":{"usedBytes":17297235968,"totalBytes":34107396096},
     "gpu":{"name":"NVIDIA GeForce RTX 5070","percent":0,"memoryUsedBytes":6136266752,"memoryTotalBytes":12820938752,
            "temperatureC":49,"powerW":1.9,"fanPercent":0},
     "network":{"downBytesPerSec":1629,"upBytesPerSec":621,"adapters":["Wi-Fi"]},
     "disks":[{"drives":["C:"],"model":"ADATA LEGEND 800","kind":"ssd","usedBytes":689329963008,"totalBytes":999036022784,
               "readBytesPerSec":144884,"writeBytesPerSec":3204045,"busyPercent":0.7,"temperatureC":48,
               "temperatureAt":"2026-11-21T14:15:45.170Z"},
              {"drives":["D:"],"model":"WDC WD5000AAKX-003CA0","kind":null,"usedBytes":166625280,"totalBytes":500104687616,
               "readBytesPerSec":0,"writeBytesPerSec":0,"busyPercent":0.1,"temperatureC":40,
               "temperatureAt":"2026-11-21T14:15:45.170Z"}],
     "unknown":{"cpu.temperatureC":"Core Temp is not running"}}
    """

    func testParsesARealReading() throws {
        let stats = try PCStatsParsing.parse(Data(reading.utf8))
        XCTAssertEqual(try XCTUnwrap(stats.at).timeIntervalSince1970, 1_795_270_603.492, accuracy: 0.001)
        XCTAssertEqual(stats.cpu?.percent, 5)
        XCTAssertNil(stats.cpu?.temperatureC)
        XCTAssertEqual(stats.unknown["cpu.temperatureC"], "Core Temp is not running")
        XCTAssertEqual(stats.memory?.totalBytes, 34_107_396_096)
        XCTAssertEqual(stats.gpu?.name, "NVIDIA GeForce RTX 5070")
        XCTAssertEqual(stats.gpu?.percent, 0, "a real 0 stays 0")
        XCTAssertEqual(stats.network?.adapters, ["Wi-Fi"])
        XCTAssertEqual(stats.disks.map(\.id), ["C:", "D:"])
        XCTAssertEqual(stats.disks[0].kind, "ssd")
        XCTAssertNil(stats.disks[1].kind)
        XCTAssertEqual(stats.disks[1].temperatureC, 40)
    }

    func testMissingSectionsAreUnknownNotZero() throws {
        let body = #"{"schema":"jorah-pcstats/1","cpu":{"percent":"high"},"memory":null,"gpu":null,"disks":[{"drives":[]}],"unknown":{"gpu":"nvidia-smi failed"}}"#
        let stats = try PCStatsParsing.parse(Data(body.utf8))
        XCTAssertNil(stats.cpu?.percent, "a string is not a number")
        XCTAssertNil(stats.memory)
        XCTAssertNil(stats.gpu)
        XCTAssertNil(stats.network)
        XCTAssertTrue(stats.disks.isEmpty, "a disk with no drive letter is dropped")
        XCTAssertEqual(stats.unknown["gpu"], "nvidia-smi failed")
        XCTAssertNil(PCFormat.percent(stats.cpu?.percent))
        XCTAssertNil(PCFormat.usage(nil, of: 10))
    }

    func testRejectsOtherSchemasAndNonJSON() {
        XCTAssertThrowsError(try PCStatsParsing.parse(Data(#"{"schema":"jorah-pcstats/2"}"#.utf8))) {
            XCTAssertEqual($0 as? PCStatsParsing.Failure, .wrongSchema("jorah-pcstats/2"))
        }
        XCTAssertThrowsError(try PCStatsParsing.parse(Data("<html>502</html>".utf8))) {
            XCTAssertEqual($0 as? PCStatsParsing.Failure, .notJSON)
        }
    }

    func testBooleansAreNotNumbersAndTextIsCleaned() throws {
        let body = "{\"schema\":\"jorah-pcstats/1\",\"cpu\":{\"percent\":true,\"name\":\"Intel\\u202e\\u0007 CPU\"},\"disks\":[]}"
        let stats = try PCStatsParsing.parse(Data(body.utf8))
        XCTAssertNil(stats.cpu?.percent)
        XCTAssertEqual(stats.cpu?.name, "Intel CPU")
    }

    func testFormats() {
        XCTAssertEqual(PCFormat.percent(12.6), "13%")
        XCTAssertEqual(PCFormat.celsius(48.4), "48°C")
        XCTAssertEqual(PCFormat.usage(17_297_235_968, of: 34_107_396_096), "17.3 / 34.1 GB")
        XCTAssertEqual(PCFormat.usage(689_329_963_008, of: 999_036_022_784), "689 / 999 GB")
        XCTAssertEqual(PCFormat.usage(1_500_000_000_000, of: 2_000_000_000_000), "1.50 / 2.00 TB")
        XCTAssertEqual(PCFormat.rate(0), "0 B/s")
        XCTAssertEqual(PCFormat.rate(1629), "1.6 KB/s")
        XCTAssertEqual(PCFormat.rate(3_204_045), "3.2 MB/s")
        XCTAssertEqual(PCFormat.rate(144_884), "145 KB/s")
        XCTAssertNil(PCFormat.rate(nil))
        XCTAssertEqual(PCFormat.fraction(5, of: 10), 0.5)
        XCTAssertEqual(PCFormat.fraction(15, of: 10), 1)
        XCTAssertNil(PCFormat.fraction(5, of: 0))
    }
}
