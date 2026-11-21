import Foundation

/// Which set of settings and Keychain items this copy of the HUD uses.
///
/// `JORAH_HUD_PROFILE=test` keeps a test copy's pairing, device key and settings apart from the
/// everyday HUD (Keychain service `jorah-hud-test`, defaults suite `dev.jorah.hud.test`), so a run
/// against a scratch Gateway never replaces the live pairing. Unset, the HUD uses `jorah-hud` and
/// the standard defaults, as it always has.
enum HUDProfile {
    static let name: String? = {
        guard let raw = ProcessInfo.processInfo.environment["JORAH_HUD_PROFILE"], !raw.isEmpty,
              raw.count <= 20, raw.allSatisfy({ $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "-") })
        else { return nil }
        return raw
    }()

    static let keychainService: String = name.map { "jorah-hud-\($0)" } ?? "jorah-hud"

    static let defaults: UserDefaults = {
        guard let name, let suite = UserDefaults(suiteName: "dev.jorah.hud.\(name)") else { return .standard }
        return suite
    }()
}
