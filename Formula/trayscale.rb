class Trayscale < Formula
  desc "Unofficial GUI interface for the Tailscale daemon"
  homepage "https://github.com/DeedleFake/trayscale"
  url "https://github.com/thormme/trayscale.git",
      tag:      "master"
  license "BSD-3-Clause"
  version "v0.18.5"

  livecheck do
    url "https://github.com/DeedleFake/trayscale"
    regex(/^v?(\d+(?:\.\d+)+)$/i)
    strategy :github_latest
  end

#   bottle do
#     sha256 cellar: :any_skip_relocation, arm64_tahoe:   "89b7991f9aa226c4bc1e8920e1c626e7599af0dacb15d4849e818e61a3efead4"
#     sha256 cellar: :any_skip_relocation, arm64_sequoia: "dd4184c80c37011040d49693434fb6d05adb6f5b89525f2f5e25aaa79e9f7872"
#     sha256 cellar: :any_skip_relocation, arm64_sonoma:  "2c51ed0928285b11e5b8490961a061e4abd4a9ef84a5733f6cd1f04709198224"
#     sha256 cellar: :any_skip_relocation, sonoma:        "c209c4ee26ded785b2893d9e8ec2745fca795b0a872228f64c79e62edbb85f1f"
#     sha256 cellar: :any_skip_relocation, arm64_linux:   "9a029c6d22022602d8e86f7f582d8deaf925a5be90daeacbb9eb2229a3d1a360"
#     sha256 cellar: :any_skip_relocation, x86_64_linux:  "9a0fc1d71206b6ace0526d9c2650abd9da7d139228aeca01a4ec8ed9531ff126"
#   end

  depends_on "go" => :build
  depends_on "libadwaita"
  depends_on "gtk4"
  depends_on "gobject-introspection"
  depends_on "harfbuzz"
  depends_on "appstream"

  # conflicts_with cask: "tailscale-app"

  def install

    metainfo = File.read("dev.deedles.Trayscale.metainfo.xml")
    app_version = metainfo[/<release\s+version="([^"]+)"/, 1] || version

    ldflags = %W[
      -s -w
      -X deedles.dev/trayscale/internal/metadata.version=#{app_version}
    ]
      
    system "go", "build", *std_go_args(ldflags:, output: "trayscale"), "./cmd/trayscale"

    # Install binary to libexec (actual executable)
    libexec.install "trayscale"

    # Create wrapper script to set up environment
    (bin/"trayscale").write <<~EOS
      #!/bin/bash
      export XDG_DATA_DIRS="#{HOMEBREW_PREFIX}/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
      exec "#{libexec}/trayscale" "$@"
    EOS
    
    # Install GLib schema
    (share/"glib-2.0/schemas").install "dev.deedles.Trayscale.gschema.xml"

    # Create .app bundle
    app = prefix/"Trayscale.app/Contents"
    app.mkpath
    (app/"MacOS").mkpath
    (app/"Resources").mkpath

    (app/"Info.plist").write <<~XML
      <?xml version="1.0" encoding="UTF-8"?>
      <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
      <plist version="1.0">
      <dict>
        <key>CFBundleExecutable</key>
        <string>trayscale</string>
        <key>CFBundleIdentifier</key>
        <string>dev.deedles.Trayscale</string>
        <key>CFBundleName</key>
        <string>Trayscale</string>
        <key>CFBundleVersion</key>
        <string>#{app_version}</string>
        <key>CFBundleShortVersionString</key>
        <string>#{app_version}</string>
        <key>CFBundleIconFile</key>
        <string>AppIcon</string>
        <key>CFBundlePackageType</key>
        <string>APPL</string>
        <key>NSHighResolutionCapable</key>
        <true/>
        <key>LSUIElement</key>
        <true/>
      </dict>
      </plist>
    XML

    # Create launcher script inside .app
    (app/"MacOS/trayscale").write <<~EOS
      #!/bin/bash
      export XDG_DATA_DIRS="#{HOMEBREW_PREFIX}/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
      exec "#{libexec}/trayscale" "$@"
    EOS
    (app/"MacOS/trayscale").chmod 0755

    # Copy icon (convert PNG to icns if needed, or use existing)
    cp "dev.deedles.Trayscale.png", app/"Resources/AppIcon.png"

  end

#   test do
#     # Basic test that the binary runs
#     assert_match "Usage", shell_output("#{bin}/trayscale --help", 2)
#   end

  def post_install
    system "cp", "-r", "#{prefix}/Trayscale.app", "/Applications/"
  rescue
    opoo "Could not copy to /Applications. Run: cp -r #{prefix}/Trayscale.app /Applications/"
  end

  def post_uninstall
    rm_f "/Applications/Trayscale.app"
  rescue
    opoo "Could not remove Trayscale.app. Run: sudo rm -rf /Applications/Trayscale.app"
  end
end