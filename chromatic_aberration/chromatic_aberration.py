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
import traceback

class ChromaticAberration(Gimp.PlugIn):
    ## GimpPlugIn virtual methods ##
    def do_query_procedures(self):
        return ["plug-in-chromatic-aberration"]

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            self.run, None)
        
        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
        
        procedure.set_menu_label("Chromatic Aberration")
        procedure.add_menu_path("<Image>/Filters/Custom/")
        
        procedure.set_documentation("True 3-layer chromatic aberration channel splitting",
                                    "Isolates RGB layers using flawless Multiply-Merge math, applies offsets, and re-blends via Addition",
                                    name)
        procedure.set_attribution("GIMP 3.0 Dev", "GIMP 3.0 Dev", "2026")

        # --- PARAMETERS ---
        procedure.add_int_argument("red-x", "Red X Offset (px)", "Horizontal shift for Red layer", -500, 500, 15, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("red-y", "Red Y Offset (px)", "Vertical shift for Red layer", -500, 500, 0, GObject.ParamFlags.READWRITE)
        
        procedure.add_int_argument("green-x", "Green X Offset (px)", "Horizontal shift for Green layer", -500, 500, 0, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("green-y", "Green Y Offset (px)", "Vertical shift for Green layer", -500, 500, 0, GObject.ParamFlags.READWRITE)
        
        procedure.add_int_argument("blue-x", "Blue X Offset (px)", "Horizontal shift for Blue layer", -500, 500, -15, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("blue-y", "Blue Y Offset (px)", "Vertical shift for Blue layer", -500, 500, 0, GObject.ParamFlags.READWRITE)
        
        return procedure

    def run(self, procedure, run_mode, image, drawables, config, run_data):
        if len(drawables) != 1:
            error = GLib.Error.new_literal(Gimp.PlugIn.error_quark(), "Requires exactly one active layer.", 0)
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

        # --- GENERATE GUI ---
        if run_mode == Gimp.RunMode.INTERACTIVE:
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk
            
            GimpUi.init("chromatic_aberration")
            dialog = GimpUi.ProcedureDialog.new(procedure, config)
            dialog.fill(None)
            
            if not dialog.run():
                dialog.destroy()
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            dialog.destroy()

        # --- EXTRACT GUI VALUES ---
        red_x = config.get_property("red-x")
        red_y = config.get_property("red-y")
        green_x = config.get_property("green-x")
        green_y = config.get_property("green-y")
        blue_x = config.get_property("blue-x")
        blue_y = config.get_property("blue-y")

        base_layer = drawables[0]

        image.undo_group_start()
        Gimp.context_push()

        try:
            Gegl.init(None)

            # Unbreakable Multiply-Merge mathematical isolation function
            def create_isolated_channel(channel_name, hex_color):
                channel_layer = Gimp.Layer.new_from_drawable(base_layer, image)
                image.insert_layer(channel_layer, None, 0)
                if not channel_layer.has_alpha():
                    channel_layer.add_alpha()

                width = channel_layer.get_width()
                height = channel_layer.get_height()
                
                solid_overlay = Gimp.Layer.new(image, f"{channel_name} Overlay", width, height, Gimp.ImageType.RGBA_IMAGE, 100.0, Gimp.LayerMode.MULTIPLY)
                
                _, cx, cy = channel_layer.get_offsets()
                solid_overlay.set_offsets(cx, cy)
                image.insert_layer(solid_overlay, None, 0)

                old_fg = Gimp.context_get_foreground()
                Gimp.context_set_foreground(Gegl.Color.new(hex_color))
                solid_overlay.edit_fill(Gimp.FillType.FOREGROUND)
                Gimp.context_set_foreground(old_fg)

                merged_layer = image.merge_down(solid_overlay, Gimp.MergeType.CLIP_TO_BOTTOM_LAYER)
                merged_layer.set_name(f"{channel_name} Channel Split")
                
                return merged_layer

            # --- STEP 1: GENERATE STACK LAYERS (Bottom to Top) ---
            # GIMP places newer layers at index 0 (the top). 
            # To get Green at the absolute bottom, we build it first.
            green_layer = create_isolated_channel("Green", "#00FF00")
            
            # Blue goes next, pushing Green down into index 1
            blue_layer = create_isolated_channel("Blue", "#0000FF")
            
            # Red goes last, sitting beautifully at the top (index 0)
            red_layer = create_isolated_channel("Red", "#FF0000")

            # --- STEP 2: APPLY OFFSETS FROM THE SLIDERS ---
            _, r_cx, r_cy = red_layer.get_offsets()
            red_layer.set_offsets(r_cx + red_x, r_cy + red_y)

            _, b_cx, b_cy = blue_layer.get_offsets()
            blue_layer.set_offsets(b_cx + blue_x, b_cy + blue_y)

            _, g_cx, g_cy = green_layer.get_offsets()
            green_layer.set_offsets(g_cx + green_x, g_cy + green_y)

            # --- STEP 3: ENFORCE ADDITION BLEND MODES ---
            red_layer.set_mode(Gimp.LayerMode.ADDITION)
            blue_layer.set_mode(Gimp.LayerMode.ADDITION)
            green_layer.set_mode(Gimp.LayerMode.ADDITION)

            # Hide original base layer to prevent background transparency conflicts
            base_layer.set_visible(False)

        except Exception as err:
            error_msg = "".join(traceback.format_exception(type(err), err, err.__traceback__))
            Gimp.message(f"Chromatic Aberration Error:\n{error_msg}")
            
        finally:
            image.select_rectangle(Gimp.ChannelOps.REPLACE, 0, 0, 0, 0)
            Gimp.context_pop()
            image.undo_group_end()

        Gimp.displays_flush()

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

Gimp.main(ChromaticAberration.__gtype__, sys.argv)