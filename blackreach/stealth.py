"""
Stealth Module - Bot Detection Evasion

Techniques to avoid detection by anti-bot systems:
- User agent rotation
- Human-like mouse movements and timing
- Browser fingerprint randomization
- Proxy rotation
- Stealth browser configuration
"""

import random
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field


@dataclass
class StealthConfig:
    """Configuration for stealth behavior."""
    # Timing
    min_delay: float = 0.5
    max_delay: float = 2.0
    typing_speed: Tuple[float, float] = (0.05, 0.15)  # seconds per char
    
    # Mouse behavior
    human_mouse: bool = True
    mouse_jitter: int = 3  # pixels of random movement
    
    # Browser fingerprint
    randomize_viewport: bool = True
    randomize_user_agent: bool = True
    
    # Resources
    block_images: bool = False
    block_fonts: bool = False
    block_media: bool = True
    block_tracking: bool = True
    
    # Proxy
    proxy: Optional[str] = None
    proxy_rotation: List[str] = field(default_factory=list)


# Common user agents (updated January 2026)
USER_AGENTS = [
    # Chrome 133+ on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    # Firefox 134+ on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:134.0) Gecko/20100101 Firefox/134.0",
    # Safari 18+ on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
]

# Common viewport sizes
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
    {"width": 2560, "height": 1440},
]

# Tracking/analytics domains to block
BLOCKED_DOMAINS = [
    "google-analytics.com", "googletagmanager.com", "facebook.net",
    "doubleclick.net", "analytics.", "tracking.", "pixel.",
    "hotjar.com", "mixpanel.com", "segment.io", "amplitude.com",
]


class Stealth:
    """Stealth utilities for evading bot detection."""
    
    def __init__(self, config: Optional[StealthConfig] = None):
        self.config = config or StealthConfig()
        self._current_proxy_index = 0
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        return random.choice(USER_AGENTS)
    
    def get_random_viewport(self) -> Dict[str, int]:
        """Get a random viewport size."""
        return random.choice(VIEWPORTS).copy()
    
    def get_next_proxy(self) -> Optional[str]:
        """Get next proxy from rotation list."""
        if not self.config.proxy_rotation:
            return self.config.proxy
        proxy = self.config.proxy_rotation[self._current_proxy_index]
        self._current_proxy_index = (self._current_proxy_index + 1) % len(self.config.proxy_rotation)
        return proxy
    
    def random_delay(self, min_s: float = None, max_s: float = None) -> float:
        """Get a random delay duration."""
        min_s = min_s or self.config.min_delay
        max_s = max_s or self.config.max_delay
        return random.uniform(min_s, max_s)
    
    def typing_delay(self) -> float:
        """Get delay between keystrokes for human-like typing."""
        min_d, max_d = self.config.typing_speed
        return random.uniform(min_d, max_d)
    
    def should_block_url(self, url: str) -> bool:
        """Check if URL should be blocked (tracking, ads, etc.)."""
        if not self.config.block_tracking:
            return False
        return any(domain in url.lower() for domain in BLOCKED_DOMAINS)
    
    def get_resource_types_to_block(self) -> List[str]:
        """Get list of resource types to block."""
        blocked = []
        if self.config.block_images:
            blocked.append("image")
        if self.config.block_fonts:
            blocked.append("font")
        if self.config.block_media:
            blocked.extend(["media", "websocket"])
        return blocked

    def generate_bezier_path(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        num_points: int = 20
    ) -> List[Tuple[float, float]]:
        """
        Generate human-like mouse path using Bezier curves.
        Humans don't move in straight lines - they curve.
        """
        # Add some randomness to control points
        dx = end[0] - start[0]
        dy = end[1] - start[1]

        # Random control points for the curve
        ctrl1 = (
            start[0] + dx * random.uniform(0.2, 0.4) + random.uniform(-50, 50),
            start[1] + dy * random.uniform(0.2, 0.4) + random.uniform(-50, 50)
        )
        ctrl2 = (
            start[0] + dx * random.uniform(0.6, 0.8) + random.uniform(-50, 50),
            start[1] + dy * random.uniform(0.6, 0.8) + random.uniform(-50, 50)
        )

        points = []
        for i in range(num_points + 1):
            t = i / num_points
            # Cubic Bezier formula
            x = (1-t)**3 * start[0] + 3*(1-t)**2*t * ctrl1[0] + 3*(1-t)*t**2 * ctrl2[0] + t**3 * end[0]
            y = (1-t)**3 * start[1] + 3*(1-t)**2*t * ctrl1[1] + 3*(1-t)*t**2 * ctrl2[1] + t**3 * end[1]

            # Add micro-jitter for realism
            if self.config.mouse_jitter and i > 0 and i < num_points:
                x += random.uniform(-self.config.mouse_jitter, self.config.mouse_jitter)
                y += random.uniform(-self.config.mouse_jitter, self.config.mouse_jitter)

            points.append((x, y))

        return points

    def generate_scroll_pattern(self, total_distance: int) -> List[int]:
        """
        Generate human-like scroll pattern.
        Humans scroll in bursts, not smooth continuous motion.
        """
        scrolls = []
        remaining = abs(total_distance)
        direction = 1 if total_distance > 0 else -1

        while remaining > 0:
            # Vary scroll amounts - sometimes big, sometimes small
            if random.random() < 0.3:
                # Small adjustment scroll
                amount = random.randint(20, 80)
            else:
                # Normal scroll
                amount = random.randint(100, 300)

            amount = min(amount, remaining)
            scrolls.append(amount * direction)
            remaining -= amount

        return scrolls

    def get_stealth_scripts(self) -> List[str]:
        """
        JavaScript to inject for hiding automation.
        These override properties that bot detectors check.
        """
        scripts = []

        # Hide webdriver property
        scripts.append("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # Fake plugins (Chrome-like)
        scripts.append("""
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
                    ];
                    plugins.length = 3;
                    return plugins;
                }
            });
        """)

        # Fake languages
        scripts.append("""
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en', 'en-GB']
            });
        """)

        # Hide automation-related Chrome properties
        scripts.append("""
            window.chrome = {
                runtime: { id: undefined },
                loadTimes: function() { return {}; },
                csi: function() { return {}; },
                app: { isInstalled: false }
            };
        """)

        # Fake permissions API
        scripts.append("""
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        # Hardware concurrency (randomize CPU cores)
        scripts.append(f"""
            Object.defineProperty(navigator, 'hardwareConcurrency', {{
                get: () => {random.choice([4, 6, 8, 12, 16])}
            }});
        """)

        # Device memory (randomize)
        scripts.append(f"""
            Object.defineProperty(navigator, 'deviceMemory', {{
                get: () => {random.choice([4, 8, 16, 32])}
            }});
        """)

        # Platform (consistent with user agent)
        scripts.append("""
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });
        """)

        return scripts

    def get_canvas_spoofing_script(self) -> str:
        """
        Canvas fingerprint spoofing.
        Adds subtle noise to canvas operations to create unique fingerprints.
        """
        # Random noise seed for this session
        noise_seed = random.randint(1, 1000000)

        return f"""
        (function() {{
            const NOISE_SEED = {noise_seed};

            // Simple seeded random for consistent noise per session
            function seededRandom(seed) {{
                const x = Math.sin(seed) * 10000;
                return x - Math.floor(x);
            }}

            // Add noise to image data
            function addNoise(imageData, seed) {{
                const data = imageData.data;
                for (let i = 0; i < data.length; i += 4) {{
                    // Very subtle noise (1-2 bits)
                    const noise = Math.floor(seededRandom(seed + i) * 3) - 1;
                    data[i] = Math.max(0, Math.min(255, data[i] + noise));     // R
                    data[i+1] = Math.max(0, Math.min(255, data[i+1] + noise)); // G
                    data[i+2] = Math.max(0, Math.min(255, data[i+2] + noise)); // B
                }}
                return imageData;
            }}

            // Override toDataURL
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type, quality) {{
                const ctx = this.getContext('2d');
                if (ctx) {{
                    try {{
                        const imageData = ctx.getImageData(0, 0, this.width, this.height);
                        addNoise(imageData, NOISE_SEED);
                        ctx.putImageData(imageData, 0, 0);
                    }} catch(e) {{}}
                }}
                return originalToDataURL.apply(this, arguments);
            }};

            // Override toBlob
            const originalToBlob = HTMLCanvasElement.prototype.toBlob;
            HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {{
                const ctx = this.getContext('2d');
                if (ctx) {{
                    try {{
                        const imageData = ctx.getImageData(0, 0, this.width, this.height);
                        addNoise(imageData, NOISE_SEED);
                        ctx.putImageData(imageData, 0, 0);
                    }} catch(e) {{}}
                }}
                return originalToBlob.apply(this, arguments);
            }};

            // Override getImageData to return noised data
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            CanvasRenderingContext2D.prototype.getImageData = function() {{
                const imageData = originalGetImageData.apply(this, arguments);
                return addNoise(imageData, NOISE_SEED);
            }};
        }})();
        """

    def get_webgl_spoofing_script(self) -> str:
        """
        WebGL fingerprint spoofing.
        Spoofs WebGL renderer and vendor info.
        """
        # Common GPU configurations to mimic
        gpu_configs = [
            {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
            {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
            {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 580 Series Direct3D11 vs_5_0 ps_5_0, D3D11)"},
            {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"},
            {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
        ]

        config = random.choice(gpu_configs)

        return f"""
        (function() {{
            const VENDOR = "{config['vendor']}";
            const RENDERER = "{config['renderer']}";

            // Override WebGL getParameter
            const getParameterOriginal = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                // UNMASKED_VENDOR_WEBGL
                if (parameter === 37445) return VENDOR;
                // UNMASKED_RENDERER_WEBGL
                if (parameter === 37446) return RENDERER;
                return getParameterOriginal.apply(this, arguments);
            }};

            // Override WebGL2 getParameter
            if (typeof WebGL2RenderingContext !== 'undefined') {{
                const getParameter2Original = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = function(parameter) {{
                    if (parameter === 37445) return VENDOR;
                    if (parameter === 37446) return RENDERER;
                    return getParameter2Original.apply(this, arguments);
                }};
            }}

            // Spoof getExtension for debug info
            const getExtensionOriginal = WebGLRenderingContext.prototype.getExtension;
            WebGLRenderingContext.prototype.getExtension = function(name) {{
                const ext = getExtensionOriginal.apply(this, arguments);
                if (name === 'WEBGL_debug_renderer_info' && ext) {{
                    return {{
                        UNMASKED_VENDOR_WEBGL: 37445,
                        UNMASKED_RENDERER_WEBGL: 37446
                    }};
                }}
                return ext;
            }};
        }})();
        """

    def get_audio_spoofing_script(self) -> str:
        """
        AudioContext fingerprint spoofing.
        Adds noise to audio processing to prevent fingerprinting.
        """
        noise_amount = random.uniform(0.00001, 0.0001)

        return f"""
        (function() {{
            const NOISE = {noise_amount};

            // Override AudioBuffer getChannelData
            const originalGetChannelData = AudioBuffer.prototype.getChannelData;
            AudioBuffer.prototype.getChannelData = function(channel) {{
                const data = originalGetChannelData.apply(this, arguments);
                // Add tiny noise to audio data
                for (let i = 0; i < data.length; i++) {{
                    data[i] += (Math.random() - 0.5) * NOISE;
                }}
                return data;
            }};

            // Override AnalyserNode getFloatFrequencyData
            const originalGetFloatFrequencyData = AnalyserNode.prototype.getFloatFrequencyData;
            AnalyserNode.prototype.getFloatFrequencyData = function(array) {{
                originalGetFloatFrequencyData.apply(this, arguments);
                for (let i = 0; i < array.length; i++) {{
                    array[i] += (Math.random() - 0.5) * NOISE * 100;
                }}
            }};

            // Override OfflineAudioContext
            if (typeof OfflineAudioContext !== 'undefined') {{
                const originalStartRendering = OfflineAudioContext.prototype.startRendering;
                OfflineAudioContext.prototype.startRendering = function() {{
                    return originalStartRendering.apply(this, arguments).then(buffer => {{
                        // Add noise to rendered audio
                        for (let c = 0; c < buffer.numberOfChannels; c++) {{
                            const data = buffer.getChannelData(c);
                            for (let i = 0; i < data.length; i++) {{
                                data[i] += (Math.random() - 0.5) * NOISE;
                            }}
                        }}
                        return buffer;
                    }});
                }};
            }}
        }})();
        """

    def get_font_spoofing_script(self) -> str:
        """
        Font fingerprint mitigation.
        Makes font detection less reliable.
        """
        return """
        (function() {
            // Randomize font measurement slightly
            const originalOffsetWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth');
            const originalOffsetHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');

            Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
                get: function() {
                    const width = originalOffsetWidth.get.call(this);
                    // Add tiny random offset for text elements
                    if (this.tagName === 'SPAN' && this.textContent.length < 20) {
                        return width + (Math.random() < 0.5 ? 0 : 1);
                    }
                    return width;
                }
            });

            Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
                get: function() {
                    const height = originalOffsetHeight.get.call(this);
                    if (this.tagName === 'SPAN' && this.textContent.length < 20) {
                        return height + (Math.random() < 0.5 ? 0 : 1);
                    }
                    return height;
                }
            });
        })();
        """

    def get_timezone_spoofing_script(self, timezone: str = "America/New_York") -> str:
        """
        Timezone spoofing.
        Makes the browser appear to be in a different timezone.
        """
        # Map timezone to offset
        tz_offsets = {
            "America/New_York": -5,
            "America/Los_Angeles": -8,
            "America/Chicago": -6,
            "Europe/London": 0,
            "Europe/Paris": 1,
            "Europe/Berlin": 1,
            "Asia/Tokyo": 9,
            "Asia/Shanghai": 8,
        }
        offset = tz_offsets.get(timezone, 0) * 60  # Convert to minutes

        return f"""
        (function() {{
            const TARGET_TZ = "{timezone}";
            const OFFSET = {offset};

            // Override getTimezoneOffset
            Date.prototype.getTimezoneOffset = function() {{
                return -OFFSET;
            }};

            // Override Intl.DateTimeFormat resolvedOptions
            const originalResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
            Intl.DateTimeFormat.prototype.resolvedOptions = function() {{
                const options = originalResolvedOptions.apply(this, arguments);
                options.timeZone = TARGET_TZ;
                return options;
            }};
        }})();
        """

    def get_all_stealth_scripts(self) -> List[str]:
        """Get all stealth scripts combined."""
        scripts = self.get_stealth_scripts()
        scripts.append(self.get_canvas_spoofing_script())
        scripts.append(self.get_webgl_spoofing_script())
        scripts.append(self.get_audio_spoofing_script())
        scripts.append(self.get_font_spoofing_script())
        scripts.append(self.get_timezone_spoofing_script())
        return scripts

