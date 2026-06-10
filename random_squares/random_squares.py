#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl
from gi.repository import GObject
from gi.repository import GLib

import sys
import random

class UltimateGlitchSquares(Gimp.PlugIn):
    ## GimpPlugIn virtual methods ##
    def do_query_procedures(self):
        return ["plug-in-ultimate-glitch-squares"]

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            self.run, None)
        
        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
        
        procedure.set_menu_label("Random Squares")
        procedure.add_menu_path("<Image>/Filters/Custom/")
        
        procedure.set_documentation("Ultimate color and blend glitch pattern generator",
                                    "Generates highly tailored erratic color blocks for glitch art",
                                    name)
        procedure.set_attribution("GIMP 3.0 Dev", "GIMP 3.0 Dev", "2026")

        # --- PARAMETERS ---
        procedure.add_int_argument("num-squares", "Number of squares", "How many squares to render", 1, 5000, 150, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("min-size", "Minimum Size (px)", "Smallest square size", 0, 4096, 10, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("max-size", "Maximum Size (px)", "Largest square size", 0, 4096, 250, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("random-opacity", "Randomize Opacity", "Vary the transparency of each square", True, GObject.ParamFlags.READWRITE)
        
        # New Feature Toggle
        procedure.add_boolean_argument("edge-bleed", "Bleed Past Edges", "Allow squares to cross canvas borders for full coverage", False, GObject.ParamFlags.READWRITE)

        # Expanded Creative Palettes Dropdown
        palette_choice = Gimp.Choice.new()
        palette_choice.add("random", 0, "Full Matrix Random", "Completely unconstrained RGB generation")
        palette_choice.add("cmyk", 1, "CMYK (Classic Print Glitch)", "Pure Cyan, Magenta, Yellow, White, Black")
        palette_choice.add("rgb", 2, "RGB (CRT/Screen Artifact)", "Pure Red, Green, Blue, White, Black")
        palette_choice.add("vaporwave", 3, "Vaporwave (Neon Pastel)", "Hot Pink, Neon Purple, Bright Teal, Dark Violet")
        palette_choice.add("toxic_sludge", 4, "Toxic Sludge (Radioactive)", "Acid Green, Deep Olive, Safety Orange, Jet Black")
        palette_choice.add("cyber_punk", 5, "Cyberpunk 2077 (High-Vis Night)", "Neon Yellow, Electric Blue, Hot Magenta, Dark Slate")
        palette_choice.add("solar_flare", 6, "Solar Flare (Thermal Glitch)", "Deep Crimson, Molten Gold, Safety Yellow, Ash Gray")
        palette_choice.add("frozen_ram", 7, "Frozen RAM (Cold Hardware)", "Glacial Blue, Ice Mint, Frost White, Deep Cobalt")
        palette_choice.add("monochrome", 8, "Monochrome (High Contrast Stark)", "Pure White, Pure Black, and harsh Grays")
        procedure.add_choice_argument("palette-type", "Color Palette", "Choose the glitch color scheme", palette_choice, "random", GObject.ParamFlags.READWRITE)

        # Blend Mode Dropdown
        blend_choice = Gimp.Choice.new()
        blend_choice.add("normal", 0, "Normal (Overlay)", "Standard stacking")
        blend_choice.add("difference", 1, "Difference (Invert)", "Flips colors on overlap - massive artifacting")
        blend_choice.add("exclusion", 2, "Exclusion (Muted Invert)", "Similar to difference but lower contrast/cyberpunk vibe")
        blend_choice.add("xor", 3, "XOR / Grain Extract", "Creates digital noise and weird negative-space math")
        procedure.add_choice_argument("blend-mode", "Blending Mode", "How squares interact with what is below them", blend_choice, "difference", GObject.ParamFlags.READWRITE)
        
        return procedure

    def run(self, procedure, run_mode, image, drawables, config, run_data):
        if len(drawables) != 1:
            error = GLib.Error.new_literal(Gimp.PlugIn.error_quark(), "Requires exactly one active layer.", 0)
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

        # --- GENERATE GUI ---
        if run_mode == Gimp.RunMode.INTERACTIVE:
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk
            
            GimpUi.init("color_glitch_squares")
            dialog = GimpUi.ProcedureDialog.new(procedure, config)
            dialog.fill(None)
            
            if not dialog.run():
                dialog.destroy()
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            dialog.destroy()

        # --- EXTRACT GUI VALUES ---
        num_squares = config.get_property("num-squares")
        min_size = config.get_property("min-size")
        max_size = config.get_property("max-size")
        use_random_opacity = config.get_property("random-opacity")
        bleed_past_edges = config.get_property("edge-bleed")
        chosen_palette = config.get_property("palette-type")
        chosen_blend = config.get_property("blend-mode")

        if min_size > max_size:
            min_size, max_size = max_size, min_size

        # --- PALETTE CONFIGURATION MAP ---
        hex_palettes = {
            "cmyk": ["#00FFFF", "#FF00FF", "#FFFF00", "#000000", "#FFFFFF"],
            "rgb": ["#FF0000", "#00FF00", "#0000FF", "#000000", "#FFFFFF"],
            "vaporwave": ["#FF6AD5", "#C774E8", "#94B3FD", "#94FFD8", "#3F3B6C"],
            "toxic_sludge": ["#39FF14", "#4A5D4E", "#FF5F1F", "#000000", "#1A1A1A"],
            "cyber_punk": ["#FFFF00", "#00E5FF", "#FF007F", "#1A1B26", "#24283B"],
            "solar_flare": ["#8B0000", "#FF4500", "#FFD700", "#FF8C00", "#2B2B2B"],
            "frozen_ram": ["#E0FFFF", "#00FFFF", "#7B68EE", "#000080", "#FFFFFF"],
            "monochrome": ["#000000", "#222222", "#888888", "#DDDDDD", "#FFFFFF"]
        }

        # --- BLEND MODE MAP ---
        blend_modes = {
            "normal": Gimp.LayerMode.NORMAL,
            "difference": Gimp.LayerMode.DIFFERENCE,
            "exclusion": Gimp.LayerMode.EXCLUSION,
            "xor": Gimp.LayerMode.GRAIN_EXTRACT
        }
        paint_mode = blend_modes.get(chosen_blend, Gimp.LayerMode.NORMAL)

        # --- RENDER ENGINE ---
        drawable = drawables[0]
        width = drawable.get_width()
        height = drawable.get_height()

        image.undo_group_start()
        Gimp.context_push()

        try:
            Gimp.context_set_paint_mode(paint_mode)

            for _ in range(num_squares):
                size = random.randint(min_size, max_size)
                
                if size == 0:
                    size = 1

                # --- EDGE COORDINATE MATH ---
                if bleed_past_edges:
                    half_size = size // 2
                    # Can start up to half-width outside the left/top edges
                    min_coord = -half_size
                    # Can end up to half-width past the right/bottom edges
                    max_x = width - half_size
                    max_y = height - half_size
                    
                    x = random.randint(min_coord, max(min_coord, max_x))
                    y = random.randint(min_coord, max(min_coord, max_y))
                else:
                    # Keep squares fully enclosed on the visible canvas area
                    x = random.randint(0, max(0, width - size))
                    y = random.randint(0, max(0, height - size))

                if use_random_opacity:
                    Gimp.context_set_opacity(random.uniform(10.0, 100.0))
                else:
                    Gimp.context_set_opacity(100.0)

                # --- COLOR RESOLUTION ---
                if chosen_palette == "random":
                    r = random.random()
                    g = random.random()
                    b = random.random()
                    random_color = Gegl.Color.new(f"rgb({r},{g},{b})")
                    Gimp.context_set_foreground(random_color)
                else:
                    current_preset = hex_palettes.get(chosen_palette, ["#000000"])
                    Gimp.context_set_foreground(Gegl.Color.new(random.choice(current_preset)))

                image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, size, size)
                drawable.edit_fill(Gimp.FillType.FOREGROUND)

        finally:
            image.select_rectangle(Gimp.ChannelOps.REPLACE, 0, 0, 0, 0)
            Gimp.context_pop()
            image.undo_group_end()

        Gimp.displays_flush()

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

Gimp.main(UltimateGlitchSquares.__gtype__, sys.argv)
