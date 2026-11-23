"""tamga ailesinin ortak paletleri (kamug / erk / yazıt ile birebir aynı tema çeşitleri ve vurgu renkleri)."""

ACCENTS = {
    "gray": "#c4c4c4",
    "red": "#ff0033",
    "blue": "#3ea6ff",
    "green": "#2ecc71",
    "orange": "#ff8a1f",
    "pink": "#ff4fa3",
    "teal": "#1fc7b6",
}


PALETTES = {
    "dark": {
        "bg": "#000000",        # AMOLED siyah
        "bg2": "#000000",
        "surface": "#272727",
        "surface_hover": "#3f3f3f",
        "card": "#212121",
        "text": "#f1f1f1",
        "text2": "#aaaaaa",
        "text3": "#717171",
        "divider": "rgba(255,255,255,0.10)",
        "hover": "rgba(255,255,255,0.10)",
        "pressed": "rgba(255,255,255,0.18)",
        "selected": "rgba(255,255,255,0.14)",
        "chip_active_bg": "#f1f1f1",
        "chip_active_fg": "#0f0f0f",
        "input_bg": "#121212",
        "input_border": "#303030",
        "button_bg": "#f1f1f1",
        "button_fg": "#0f0f0f",
        "scroll": "rgba(255,255,255,0.22)",
        "grid": "rgba(255,255,255,0.16)",
        "dock": "rgba(33,33,33,0.96)",
    },
    "light": {
        "bg": "#ffffff",
        "bg2": "#f9f9f9",
        "surface": "#f2f2f2",
        "surface_hover": "#e5e5e5",
        "card": "#ffffff",
        "text": "#0f0f0f",
        "text2": "#606060",
        "text3": "#909090",
        "divider": "rgba(0,0,0,0.10)",
        "hover": "rgba(0,0,0,0.05)",
        "pressed": "rgba(0,0,0,0.10)",
        "selected": "rgba(0,0,0,0.07)",
        "chip_active_bg": "#0f0f0f",
        "chip_active_fg": "#ffffff",
        "input_bg": "#ffffff",
        "input_border": "#d3d3d3",
        "button_bg": "#0f0f0f",
        "button_fg": "#ffffff",
        "scroll": "rgba(0,0,0,0.25)",
        "grid": "rgba(0,0,0,0.17)",
        "dock": "rgba(255,255,255,0.97)",
    },
}

# Tema çeşitleri: kimlik -> (Türkçe ad, İngilizce ad, aile, temel paletin üzerine yazılan renkler)
VARIANTS = {
    "amoled": ("AMOLED siyah", "AMOLED black", "dark", {}),
    "dark_gray": ("Koyu gri", "Dark gray", "dark", {"bg": "#0f0f0f", "bg2": "#181818"}),
    "graphite": ("Grafit", "Graphite", "dark", {
        "bg": "#1c1c1e", "bg2": "#232326", "surface": "#2f2f33", "surface_hover": "#45454a", "card": "#2a2a2e",
        "input_bg": "#18181a", "input_border": "#3a3a3e", "dock": "rgba(42,42,46,0.96)"}),
    "midnight": ("Gece mavisi", "Midnight blue", "dark", {
        "bg": "#0d1117", "bg2": "#111723", "surface": "#1f2733", "surface_hover": "#2d3846", "card": "#161d29",
        "input_bg": "#0b0f16", "input_border": "#2a3442", "text2": "#9aa6b4", "dock": "rgba(22,29,41,0.96)"}),
    "mocha": ("Sıcak koyu", "Mocha", "dark", {
        "bg": "#17130f", "bg2": "#1e1914", "surface": "#2c251e", "surface_hover": "#3d342a", "card": "#241e18",
        "input_bg": "#120f0c", "input_border": "#3a3128", "text2": "#b0a594", "dock": "rgba(36,30,24,0.96)"}),
    "white": ("Beyaz", "White", "light", {}),
    "light_gray": ("Açık gri", "Light gray", "light", {
        "bg": "#f1f1f3", "bg2": "#e9e9ec", "surface": "#e2e2e6", "surface_hover": "#d5d5da", "card": "#fafafa"}),
    "cream": ("Krem", "Cream", "light", {
        "bg": "#faf6ef", "bg2": "#f3eee4", "surface": "#ece5d8", "surface_hover": "#e0d7c6", "card": "#fffdf8",
        "input_bg": "#fffdf8", "text2": "#6b6258", "dock": "rgba(255,253,248,0.97)"}),
    "ice": ("Buz mavisi", "Ice blue", "light", {
        "bg": "#f3f7fb", "bg2": "#e9f0f7", "surface": "#e1e9f2", "surface_hover": "#d3deea", "text2": "#56657a"}),
    "mint": ("Nane", "Mint", "light", {
        "bg": "#f2f8f4", "bg2": "#e7f2eb", "surface": "#dcebe2", "surface_hover": "#cde0d4", "text2": "#56695e"}),
}
_LEGACY = {"dark": "amoled", "light": "white"}
