const { withInfoPlist } = require("expo/config-plugins");

// expo-dev-client forcibly rewrites NSAppTransportSecurity during prebuild
// (NSAllowsArbitraryLoads=false, NSAllowsLocalNetworking=true) and its plugin
// runs after app.json's infoPlist, so the only reliable override is a plugin
// placed last in the plugins array.
module.exports = function withCleartext(config) {
  return withInfoPlist(config, (c) => {
    c.modResults.NSAppTransportSecurity = {
      ...(c.modResults.NSAppTransportSecurity || {}),
      NSAllowsArbitraryLoads: true,
    };
    return c;
  });
};
