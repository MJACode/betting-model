import ExpoModulesCore
import UIKit

// The sportsbook hand-off (src/lib/openInApp.ts).
//
// `Linking.openURL` opens an https link in the app that claims it, or in
// Safari when no installed app does, and reports success either way. So the
// JS side cannot tell "the book's app opened" from "the website opened".
// `universalLinksOnly` asks iOS for the first half only: the link opens if an
// installed app claims it, and otherwise nothing opens and the answer is
// false. That answer is what sends a member without the app to the App Store.
public class OpenInAppModule: Module {
  public func definition() -> ModuleDefinition {
    Name("OpenInApp")

    AsyncFunction("openUniversalLinkOnly") { (urlString: String, promise: Promise) in
      // A string iOS cannot parse says nothing about which apps are
      // installed, so it is an error (the JS reads that as "cannot ask"),
      // never a `false`.
      guard let url = URL(string: urlString) else {
        promise.reject("ERR_OPEN_IN_APP_BAD_URL", "Not a URL")
        return
      }
      UIApplication.shared.open(url, options: [.universalLinksOnly: true]) { opened in
        promise.resolve(opened)
      }
    }.runOnQueue(.main)
  }
}
