#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
from gi.repository import GObject
from gi.repository import GLib

import sys
import random

class GlitchMask(Gimp.PlugIn):
    ## GimpPlugIn virtual methods ##
    def do_query_procedures(self):
        return ["plug-in-glitch-mask"]

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            self.run, None)
        
        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
        
        procedure.set_menu_label("Glitch Mask")
        procedure.add_menu_path("<Image>/Filters/Custom/")
        
        procedure.set_documentation("Carves custom directional geometry into the active layer",
                                    "Creates targeted horizontal, vertical, or random geometric cutouts",
                                    name)
        procedure.set_attribution("GIMP 3.0 Dev", "GIMP 3.0 Dev", "2026")

        # --- PARAMETERS ---
        procedure.add_int_argument("num-cuts", "Number of Cuts", "How many shapes to carve out", 1, 5000, 150, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("min-size", "Minimum Size (px)", "Smallest base size", 0, 4096, 10, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("max-size", "Maximum Size (px)", "Largest base size", 0, 4096, 250, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("edge-bleed", "Bleed Past Edges", "Allow cutouts to cross canvas borders", True, GObject.ParamFlags.READWRITE)

        # 3 Glitch Designer Modes
        mode_choice = Gimp.Choice.new()
        mode_choice.add("horizontal", 0, "Horizontal Mode", "Stretches shapes horizontally (Screen Tearing)")
        mode_choice.add("vertical", 1, "Vertical Mode", "Stretches shapes vertically (Data Packet Drops)")
        mode_choice.add("random", 2, "Random Mode", "Fully independent random width and height")
        procedure.add_choice_argument("mask-mode", "Glitch Designer Mode", "Directional flow of the cutouts", mode_choice, "horizontal", GObject.ParamFlags.READWRITE)
        
        return procedure

    def run(self, procedure, run_mode, image, drawables, config, run_data):
        if len(drawables) != 1:
            error = GLib.Error.new_literal(Gimp.PlugIn.error_quark(), "Requires exactly one active layer.", 0)
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

        # --- GENERATE GUI ---
        if run_mode == Gimp.RunMode.INTERACTIVE:
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk
            
            GimpUi.init("glitch_mask")
            dialog = GimpUi.ProcedureDialog.new(procedure, config)
            dialog.fill(None)
            
            if not dialog.run():
                dialog.destroy()
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            dialog.destroy()

        # --- EXTRACT GUI VALUES ---
        num_cuts = config.get_property("num-cuts")
        min_size = config.get_property("min-size")
        max_size = config.get_property("max-size")
        bleed_past_edges = config.get_property("edge-bleed")
        mask_mode = config.get_property("mask-mode")

        if min_size > max_size:
            min_size, max_size = max_size, min_size

        drawable = drawables[0]
        canvas_width = drawable.get_width()
        canvas_height = drawable.get_height()

        image.undo_group_start()
        Gimp.context_push()

        try:
            if isinstance(drawable, Gimp.Layer) and not drawable.has_alpha():
                drawable.add_alpha()

            image.select_rectangle(Gimp.ChannelOps.REPLACE, 0, 0, 0, 0)

            # --- MAIN GEOMETRY ENGINE ---
            for _ in range(num_cuts):
                # Establish a base size constraint from sliders
                base_size = random.randint(min_size, max_size)
                if base_size == 0:
                    base_size = 1

                # Calculate dimensional behavior based on selected mode
                if mask_mode == "horizontal":
                    # Width stretches out extensively past the square base
                    rect_width = random.randint(base_size, max(base_size, base_size * 5))
                    rect_height = base_size
                elif mask_mode == "vertical":
                    # Height stretches out extensively past the square base
                    rect_width = base_size
                    rect_height = random.randint(base_size, max(base_size, base_size * 5))
                else: # "random"
                    # Height and width have zero mathematical relation
                    rect_width = random.randint(min_size, max_size)
                    rect_height = random.randint(min_size, max_size)
                    if rect_width == 0: rect_width = 1
                    if rect_height == 0: rect_height = 1

                # Spatial geometry (accounting for distinct width/height)
                if bleed_past_edges:
                    half_w = rect_width // 2
                    half_h = rect_height // 2
                    
                    x = random.randint(-half_w, max(-half_w, canvas_width - half_w))
                    y = random.randint(-half_h, max(-half_h, canvas_height - half_h))
                else:
                    x = random.randint(0, max(0, canvas_width - rect_width))
                    y = random.randint(0, max(0, canvas_height - rect_height))

                # Accumulate the shape into the global mask selection
                image.select_rectangle(Gimp.ChannelOps.ADD, x, y, rect_width, rect_height)

            # Clear the entire gathered matrix cleanly
            drawable.edit_clear()

        finally:
            image.select_rectangle(Gimp.ChannelOps.REPLACE, 0, 0, 0, 0)
            Gimp.context_pop()
            image.undo_group_end()

        Gimp.displays_flush()

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

Gimp.main(GlitchMask.__gtype__, sys.argv)