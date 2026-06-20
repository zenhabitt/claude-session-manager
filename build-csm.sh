#!/bin/bash
# Build Claude Code Session Manager as a macOS .app bundle
# Usage: bash build-csm.sh [--dmg]
# Output: Claude Session Manager.app (and optionally .dmg)

set -e

APP_NAME="Claude Session Manager"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
APP_DIR="$BUILD_DIR/$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   Building macOS Application        ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Clean previous build
rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES"

# ── Step 1: Copy server.py ──────────────────────────────────────────
echo "  [1/5] Copying server.py..."
cp "$SCRIPT_DIR/server.py" "$RESOURCES/server.py"
echo "         Done"

# ── Step 2: Generate App Icon ───────────────────────────────────────
echo "  [2/5] Generating app icon..."

ICONSET="$BUILD_DIR/icon.iconset"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"

# Generate a 1024x1024 source PNG using pure Python (PPM → sips conversion)
python3 << 'PYEOF'
import subprocess, os

# Create a 1024x1024 PPM image (simple text format)
# Design: dark background with a stylized "C" chat bubble in gradient blue/purple
size = 1024
ppm_path = "/tmp/csm_icon.ppm"

# Generate pixel data
with open(ppm_path, "w") as f:
    f.write(f"P3\n{size} {size}\n255\n")
    for y in range(size):
        for x in range(size):
            # Center-relative coordinates (range -1 to 1)
            cx = (x - size/2) / (size/2)
            cy = (y - size/2) / (size/2)
            dist = (cx*cx + cy*cy) ** 0.5

            # Rounded rectangle background
            rx = abs(cx) * 1.15
            ry = abs(cy) * 1.15
            # Rounded corners (squircle effect)
            rect_dist = (rx**4 + ry**4) ** 0.25

            if rect_dist < 0.92:
                # Gradient from deep blue (top) to purple (bottom)
                t = (y / size)  # 0 at top, 1 at bottom
                r = int(45 + t * 35)
                g = int(60 + t * 15)
                b_val = int(140 - t * 40)
                # Slight inner glow
                glow = 1.0 - (rect_dist / 0.92) * 0.15
                r = int(r * glow)
                g = int(g * glow)
                b_val = int(b_val * glow)
            elif rect_dist < 1.0:
                # Anti-aliased edge
                edge_t = (rect_dist - 0.92) / 0.08
                bg_r, bg_g, bg_b = 26, 27, 30  # dark background
                t = (y / size)
                fg_r = int(45 + t * 35)
                fg_g = int(60 + t * 15)
                fg_b = int(140 - t * 40)
                r = int(fg_r * (1-edge_t) + bg_r * edge_t)
                g = int(fg_g * (1-edge_t) + bg_b * edge_t)
                b_val = int(fg_b * (1-edge_t) + bg_b * edge_t)
            else:
                r, g, b_val = 26, 27, 30  # background

            # Draw chat bubble and "C" in white
            # Chat bubble: centered circle-ish shape
            bubble_cx, bubble_cy = 0.0, -0.08
            bubble_rx2 = 0.35
            bubble_ry2 = 0.32
            bubble_dist = ((cx - bubble_cx)**2 / bubble_rx2**2 +
                           (cy - bubble_cy)**2 / bubble_ry2**2) ** 0.5

            # Small tail on bubble
            tail = False
            if 0.13 < cx < 0.22 and 0.18 < cy < 0.32:
                tail_dist = abs(cx - 0.175) / 0.05 + abs(cy - 0.25) / 0.08
                if tail_dist < 0.7:
                    tail = True

            if bubble_dist < 1.0 or tail:
                # Letter "C" inside bubble (subtractive)
                # C shape: outer circle minus inner circle, with a cut on the right
                letter_cx, letter_cy = 0.0, -0.06
                c_outer = 0.18
                c_inner = 0.11
                c_dist = ((cx - letter_cx)**2 + (cy - letter_cy)**2) ** 0.5
                is_c = c_inner < c_dist < c_outer and cx < 0.07
                # Anti-aliased C edges
                if is_c:
                    # White text
                    blend = 1.0
                    if c_dist < c_inner + 0.015:
                        blend = (c_dist - c_inner) / 0.015
                    elif c_dist > c_outer - 0.015:
                        blend = (c_outer - c_dist) / 0.015
                    blend = max(0, min(1, blend))
                    r = int(r + (240 - r) * blend)
                    g = int(g + (240 - g) * blend)
                    b_val = int(b_val + (245 - b_val) * blend)
                elif not tail and bubble_dist > 0.92:
                    # Thin border around bubble
                    r = int(r + (180 - r) * 0.3)
                    g = int(g + (200 - g) * 0.3)
                    b_val = int(b_val + (230 - b_val) * 0.3)

            # Clamp
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b_val = max(0, min(255, b_val))

            f.write(f"{r} {g} {b_val} ")

# Convert PPM to PNG using sips
subprocess.run(["sips", "-s", "format", "png", ppm_path,
                "--out", "/tmp/csm_icon_1024.png"], check=True, capture_output=True)

os.remove(ppm_path)
print("         Icon PNG generated")
PYEOF

# Generate various sizes for .iconset
sips -z 16 16   /tmp/csm_icon_1024.png --out "$ICONSET/icon_16x16.png" 2>/dev/null
sips -z 32 32   /tmp/csm_icon_1024.png --out "$ICONSET/icon_16x16@2x.png" 2>/dev/null
sips -z 32 32   /tmp/csm_icon_1024.png --out "$ICONSET/icon_32x32.png" 2>/dev/null
sips -z 64 64   /tmp/csm_icon_1024.png --out "$ICONSET/icon_32x32@2x.png" 2>/dev/null
sips -z 128 128 /tmp/csm_icon_1024.png --out "$ICONSET/icon_128x128.png" 2>/dev/null
sips -z 256 256 /tmp/csm_icon_1024.png --out "$ICONSET/icon_128x128@2x.png" 2>/dev/null
sips -z 256 256 /tmp/csm_icon_1024.png --out "$ICONSET/icon_256x256.png" 2>/dev/null
sips -z 512 512 /tmp/csm_icon_1024.png --out "$ICONSET/icon_256x256@2x.png" 2>/dev/null
sips -z 512 512 /tmp/csm_icon_1024.png --out "$ICONSET/icon_512x512.png" 2>/dev/null
cp /tmp/csm_icon_1024.png "$ICONSET/icon_512x512@2x.png"

# Create .icns from .iconset
iconutil -c icns "$ICONSET" -o "$RESOURCES/icon.icns"
rm -rf "$ICONSET" /tmp/csm_icon_1024.png

echo "         Done"

# ── Step 3: Write launcher (C stub + shell script) ────────────────
echo "  [3/5] Writing launcher..."

# Shell script (stored in Resources, invoked by C launcher as child process)
cat > "$RESOURCES/launcher.sh" << 'LAUNCHER'
#!/bin/bash

PORT=8742
URL="http://localhost:$PORT"
LOG_FILE="/tmp/claude-session-manager.log"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_PY="$SCRIPT_DIR/server.py"
MIN_LIFETIME=3  # seconds — prevent macOS from thinking app crashed

START_TIME=$(date +%s)

ensure_min_lifetime() {
    local elapsed=$(($(date +%s) - START_TIME))
    if [ $elapsed -lt $MIN_LIFETIME ]; then
        sleep $((MIN_LIFETIME - elapsed))
    fi
}

# ── Case 1: Server already running → focus browser, wait, exit ──
if curl -s --max-time 2 "$URL" > /dev/null 2>&1; then
    # Bring browser to front — activates the last-used window (our session manager tab)
    osascript -e '
      tell application "System Events"
        set browsers to {"Google Chrome", "Safari", "Arc", "Brave Browser", "Microsoft Edge"}
        repeat with b in browsers
          if exists application b then
            tell application b to activate
            exit repeat
          end if
        end repeat
      end tell
    ' 2>/dev/null
    ensure_min_lifetime
    exit 0
fi

# ── Case 2: Start fresh ──────────────────────────────────────────

# Find Python 3
PYTHON=""
for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    if [ -x "$p" ]; then
        PYTHON="$p"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    osascript -e 'display dialog "Python 3 not found.\n\nPlease install Python 3 from python.org or Homebrew (brew install python)." buttons {"OK"} default button "OK" with icon stop'
    ensure_min_lifetime
    exit 1
fi

# Start server (server.py will auto-open browser)

nohup "$PYTHON" "$SERVER_PY" > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# Wait for server to be ready
SERVER_READY=false
for i in $(seq 1 20); do
    if curl -s --max-time 1 "$URL" > /dev/null 2>&1; then
        SERVER_READY=true
        break
    fi
    sleep 0.3
done

if [ "$SERVER_READY" = false ]; then
    osascript -e 'display dialog "Failed to start session manager.\n\nCheck log: /tmp/claude-session-manager.log" buttons {"OK"} default button "OK" with icon stop'
    kill $SERVER_PID 2>/dev/null
    ensure_min_lifetime
    exit 1
fi

# Open browser via AppleScript (webbrowser may fail in background context)
sleep 1
osascript -e "tell application \"Safari\" to open location \"$URL\"" 2>/dev/null || \
osascript -e "tell application \"Google Chrome\" to open location \"$URL\"" 2>/dev/null || \
open "$URL" 2>/dev/null || true

# Stay alive — monitor server process
while kill -0 $SERVER_PID 2>/dev/null; do
    sleep 3
done

ensure_min_lifetime
exit 0
LAUNCHER

chmod +x "$RESOURCES/launcher.sh"

# Cocoa stub: minimal Objective-C app that participates in macOS event loop
# This prevents "not responding" errors on modern macOS
cat > "$BUILD_DIR/launcher_stub.m" << 'OBJC'
#import <Cocoa/Cocoa.h>
#import <stdio.h>
#import <stdlib.h>
#import <string.h>
#import <libgen.h>
#import <sys/wait.h>
#import <unistd.h>

static pid_t child_pid = 0;

static void child_exit_handler(int sig) {
    int status;
    waitpid(child_pid, &status, WNOHANG);
    [[NSApplication sharedApplication] terminate:nil];
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        // Build path to launcher.sh
        char exe_path[4096];
        strncpy(exe_path, argv[0], sizeof(exe_path) - 1);
        exe_path[sizeof(exe_path) - 1] = '\0';
        char *d = dirname(exe_path);
        char script_path[4096];
        snprintf(script_path, sizeof(script_path), "%s/../Resources/launcher.sh", d);

        // Fork child to run launcher script
        child_pid = fork();
        if (child_pid < 0) return 1;

        if (child_pid == 0) {
            // Child: execute launcher
            execl("/bin/bash", "bash", script_path, NULL);
            _exit(1);
        }

        // Parent: set up Cocoa app
        [NSApplication sharedApplication];
        [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
        [NSApp finishLaunching];

        // Watch for child exit
        signal(SIGCHLD, child_exit_handler);

        // Run the event loop
        [NSApp run];
    }
    return 0;
}
OBJC

# Compile Cocoa app (universal binary)
ARCH_FLAGS="-arch arm64"
if [ "$(uname -m)" = "arm64" ]; then
    ARCH_FLAGS="-arch arm64 -arch x86_64"
fi

clang $ARCH_FLAGS -framework Cocoa -o "$MACOS_DIR/launcher" \
    "$BUILD_DIR/launcher_stub.m" 2>&1 || \
clang -arch arm64 -framework Cocoa -o "$MACOS_DIR/launcher" \
    "$BUILD_DIR/launcher_stub.m"

rm -f "$BUILD_DIR/launcher_stub.m"
echo "         Done"

# ── Step 4: Write Info.plist ──────────────────────────────────────
echo "  [4/5] Writing Info.plist..."

cat > "$CONTENTS/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>
    <string>com.local.claude-session-manager</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>LSUIElement</key>
    <false/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

echo "         Done"

# ── Step 5: Summary ──────────────────────────────────────────────
echo "  [5/5] Finalizing..."

# Remove quarantine attribute if present
xattr -d com.apple.quarantine "$APP_DIR" 2>/dev/null || true

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   Build Complete!                   ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  App: $APP_DIR"
echo "  Size: $(du -sh "$APP_DIR" | awk '{print $1}')"
echo ""
echo "  To install:"
echo "    cp -R \"$APP_DIR\" /Applications/"
echo ""

# Optional: create DMG
if [ "$1" = "--dmg" ]; then
    echo "  [DMG] Creating disk image..."
    DMG_PATH="$BUILD_DIR/$APP_NAME.dmg"
    rm -f "$DMG_PATH"

    # Create a temporary directory for DMG contents
    DMG_SRC="$BUILD_DIR/dmg_src"
    rm -rf "$DMG_SRC"
    mkdir -p "$DMG_SRC"
    cp -R "$APP_DIR" "$DMG_SRC/"
    # Add a symlink to /Applications
    ln -s /Applications "$DMG_SRC/Applications"

    hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_SRC" \
        -ov -format UDZO "$DMG_PATH" -quiet
    rm -rf "$DMG_SRC"

    echo "  DMG:  $DMG_PATH"
    echo "  Size: $(du -sh "$DMG_PATH" | awk '{print $1}')"
    echo ""
fi

echo "  Done! ✨"
echo ""
