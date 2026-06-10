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
import traceback

class GlitchShift(Gimp.PlugIn):
    ## GimpPlugIn virtual methods ##
    def do_query_procedures(self):
        return ["plug-in-glitch-shift"]

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            self.run, None)
        
        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
        
        procedure.set_menu_label("Glitch Offset")
        procedure.add_menu_path("<Image>/Filters/Custom/")
        
        procedure.set_documentation("Offsets random geometric sections of the image",
                                    "Creates fragmentation and displacement glitches by shifting localized layers",
                                    name)
        procedure.set_attribution("GIMP 3.0 Dev", "GIMP 3.0 Dev", "2026")

        # --- PARAMETERS ---
        procedure.add_int_argument("num-shifts", "Number of Shifts", "How many blocks to displace", 1, 2000, 50, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("min-size", "Minimum Size (px)", "Smallest block size", 0, 4096, 20, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("max-size", "Maximum Size (px)", "Largest block size", 0, 4096, 300, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("max-offset", "Max Offset Distance (px)", "Maximum distance a block can shift", 0, 4096, 50, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("edge-bleed", "Bleed Past Edges", "Allow blocks to pick up data crossing canvas borders", True, GObject.ParamFlags.READWRITE)

        # 3 Glitch Designer Modes
        mode_choice = Gimp.Choice.new()
        mode_choice.add("horizontal", 0, "Horizontal Mode", "Stretches blocks horizontally (Horizontal Tearing)")
        mode_choice.add("vertical", 1, "Vertical Mode", "Stretches blocks vertically (Vertical Striation)")
        mode_choice.add("random", 2, "Random Mode", "Fully independent random width and height blocks")
        procedure.add_choice_argument("mask-mode", "Glitch Designer Mode", "Directional structure of the data shift", mode_choice, "horizontal", GObject.ParamFlags.READWRITE)
        
        return procedure

    def run(self, procedure, run_mode, image, drawables, config, run_data):
        if len(drawables) != 1:
            error = GLib.Error.new_literal(Gimp.PlugIn.error_quark(), "Requires exactly one active layer.", 0)
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

        # --- GENERATE GUI ---
        if run_mode == Gimp.RunMode.INTERACTIVE:
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk
            
            GimpUi.init("glitch_shift")
            dialog = GimpUi.ProcedureDialog.new(procedure, config)
            dialog.fill(None)
            
            if not dialog.run():
                dialog.destroy()
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            dialog.destroy()

        # --- EXTRACT GUI VALUES ---
        num_shifts = config.get_property("num-shifts")
        min_size = config.get_property("min-size")
        max_size = config.get_property("max-size")
        max_offset = config.get_property("max-offset")
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
            Gimp.context_set_paint_mode(Gimp.LayerMode.NORMAL)

            for _ in range(num_shifts):
                base_size = random.randint(min_size, max_size)
                if base_size == 0:
                    base_size = 1

                # Calculate dimensional blocks
                if mask_mode == "horizontal":
                    rect_width = random.randint(base_size, max(base_size, base_size * 5))
                    rect_height = base_size
                elif mask_mode == "vertical":
                    rect_width = base_size
                    rect_height = random.randint(base_size, max(base_size, base_size * 5))
                else:
                    rect_width = random.randint(min_size, max_size)
                    rect_height = random.randint(min_size, max_size)
                    if rect_width == 0: rect_width = 1
                    if rect_height == 0: rect_height = 1

                # Locate the block on canvas
                if bleed_past_edges:
                    half_w = rect_width // 2
                    half_h = rect_height // 2
                    x = random.randint(-half_w, max(-half_w, canvas_width - half_w))
                    y = random.randint(-half_h, max(-half_h, canvas_height - half_h))
                else:
                    x = random.randint(0, max(0, canvas_width - rect_width))
                    y = random.randint(0, max(0, canvas_height - rect_height))

                # --- SHIFT MECHANICS ---
                # 1. Capture target pixels
                image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, rect_width, rect_height)
                
                non_empty, _, _, _, _ = drawable.mask_intersect()
                if non_empty:
                    Gimp.edit_copy([drawable])
                    
                    offset_x = random.randint(-max_offset, max_offset)
                    offset_y = random.randint(-max_offset, max_offset)
                    
                    dest_x = x + offset_x
                    dest_y = y + offset_y
                    
                    pasted_layers = Gimp.edit_paste(drawable, False)
                    
                    # Extract the floating selection, translate it, and anchor it via the global function
                    if pasted_layers and len(pasted_layers) > 0:
                        floating_sel = pasted_layers[0]
                        floating_sel.set_offsets(dest_x, dest_y)
                        
                        # FIX: Call the correct top-level module function
                        Gimp.floating_sel_anchor(floating_sel)

        except Exception as err:
            error_msg = "".join(traceback.format_exception(type(err), err, err.__traceback__))
            Gimp.message(f"Glitch Shift Error:\n{error_msg}")
            
        finally:
            image.select_rectangle(Gimp.ChannelOps.REPLACE, 0, 0, 0, 0)
            Gimp.context_pop()
            image.undo_group_end()

        Gimp.displays_flush()

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

Gimp.main(GlitchShift.__gtype__, sys.argv)