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
import math
import traceback

class QuantumChannelSlip(Gimp.PlugIn):
    ## GimpPlugIn virtual methods ##
    def do_query_procedures(self):
        return ["plug-in-quantum-channel-slip"]

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            self.run, None)
        
        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
        
        procedure.set_menu_label("Quantum Channel Slip")
        procedure.add_menu_path("<Image>/Filters/Custom/")
        
        procedure.set_documentation("Analog wave desynchronization and chromatic channel slipping",
                                    "Simulates hardware horizontal, vertical, or combined sync failures along mathematical waves",
                                    name)
        procedure.set_attribution("GIMP 3.0 Dev", "GIMP 3.0 Dev", "2026")

        # --- PARAMETERS ---
        procedure.add_int_argument("num-glitches", "Glitch Frequency", "How many wave anomalies to introduce", 1, 500, 30, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("band-height", "Max Band Thickness (px)", "The maximum thickness of a shifting slice", 1, 500, 15, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("wave-amplitude", "Wave Amplitude (px)", "Maximum distance pixels slip", 0, 1024, 80, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("wave-frequency", "Wave Frequency", "How many tight ripples are in the displacement wave", 1, 50, 5, GObject.ParamFlags.READWRITE)

        # 3 Multidirectional Wave Modes
        mode_choice = Gimp.Choice.new()
        mode_choice.add("horizontal", 0, "Horizontal Wave", "Warp rows horizontally (CRT Line Jitter)")
        mode_choice.add("vertical", 1, "Vertical Wave", "Warp columns vertically (Rolling Frame Glitch)")
        mode_choice.add("combined", 2, "Combined Wave (Matrix Shear)", "Warp rows both horizontally and vertically simultaneously")
        procedure.add_choice_argument("slip-mode", "Displacement Direction", "Directional orientation of the wave distortion", mode_choice, "horizontal", GObject.ParamFlags.READWRITE)

        # Target Channel Dropdown
        channel_choice = Gimp.Choice.new()
        channel_choice.add("all", 0, "All Channels (Unified Shift)", "Displaces full color data together")
        channel_choice.add("red", 1, "Red Channel Only", "Splits the red channel out erratically")
        channel_choice.add("green", 2, "Green Channel Only", "Splits the green channel out erratically")
        channel_choice.add("blue", 3, "Blue Channel Only", "Splits the blue channel out erratically")
        procedure.add_choice_argument("target-channel", "Target Color Component", "Which data stream to destabilize", channel_choice, "red", GObject.ParamFlags.READWRITE)
        
        return procedure

    def run(self, procedure, run_mode, image, drawables, config, run_data):
        if len(drawables) != 1:
            error = GLib.Error.new_literal(Gimp.PlugIn.error_quark(), "Requires exactly one active layer.", 0)
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

        # --- GENERATE GUI ---
        if run_mode == Gimp.RunMode.INTERACTIVE:
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk
            
            GimpUi.init("quantum_channel_slip")
            dialog = GimpUi.ProcedureDialog.new(procedure, config)
            dialog.fill(None)
            
            if not dialog.run():
                dialog.destroy()
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            dialog.destroy()

        # --- EXTRACT GUI VALUES ---
        num_glitches = config.get_property("num-glitches")
        band_height = config.get_property("band-height")
        wave_amplitude = config.get_property("wave-amplitude")
        wave_frequency = config.get_property("wave-frequency")
        slip_mode = config.get_property("slip-mode")
        target_channel = config.get_property("target-channel")

        drawable = drawables[0]
        canvas_width = drawable.get_width()
        canvas_height = drawable.get_height()

        image.undo_group_start()
        Gimp.context_push()

        original_channels = {}

        try:
            Gimp.context_set_paint_mode(Gimp.LayerMode.NORMAL)

            # --- ISOLATE CHANNELS ---
            original_channels[Gimp.ChannelType.RED] = image.get_component_active(Gimp.ChannelType.RED)
            original_channels[Gimp.ChannelType.GREEN] = image.get_component_active(Gimp.ChannelType.GREEN)
            original_channels[Gimp.ChannelType.BLUE] = image.get_component_active(Gimp.ChannelType.BLUE)

            if target_channel == "red":
                image.set_component_active(Gimp.ChannelType.RED, True)
                image.set_component_active(Gimp.ChannelType.GREEN, False)
                image.set_component_active(Gimp.ChannelType.BLUE, False)
            elif target_channel == "green":
                image.set_component_active(Gimp.ChannelType.RED, False)
                image.set_component_active(Gimp.ChannelType.GREEN, True)
                image.set_component_active(Gimp.ChannelType.BLUE, False)
            elif target_channel == "blue":
                image.set_component_active(Gimp.ChannelType.RED, False)
                image.set_component_active(Gimp.ChannelType.GREEN, False)
                image.set_component_active(Gimp.ChannelType.BLUE, True)

            # --- MULTIDIRECTIONAL CORE ENGINE ---
            for _ in range(num_glitches):
                current_thickness = random.randint(1, band_height)

                # 1. Determine spatial bounds depending on whether we are slicing rows or columns
                if slip_mode == "vertical":
                    # Slice VERTICAL COLUMNS
                    start_x = random.randint(0, canvas_width)
                    if start_x + current_thickness > canvas_width:
                        current_thickness = canvas_width - start_x
                    if current_thickness <= 0: continue
                    
                    image.select_rectangle(Gimp.ChannelOps.REPLACE, start_x, 0, current_thickness, canvas_height)
                else:
                    # Slice HORIZONTAL ROWS (For Horizontal and Combined modes)
                    start_y = random.randint(0, canvas_height)
                    if start_y + current_thickness > canvas_height:
                        current_thickness = canvas_height - start_y
                    if current_thickness <= 0: continue
                    
                    image.select_rectangle(Gimp.ChannelOps.REPLACE, 0, start_y, canvas_width, current_thickness)
                
                # 2. Process displacements
                non_empty, _, _, _, _ = drawable.mask_intersect()
                if non_empty:
                    Gimp.edit_copy([drawable])
                    
                    # 3. Calculate mathematical wave outputs based on mode selection
                    if slip_mode == "horizontal":
                        wave_input = (start_y / canvas_height) * math.pi * 2 * wave_frequency
                        dest_x = int(math.sin(wave_input) * wave_amplitude)
                        dest_y = start_y
                        
                    elif slip_mode == "vertical":
                        wave_input = (start_x / canvas_width) * math.pi * 2 * wave_frequency
                        dest_x = start_x
                        dest_y = int(math.cos(wave_input) * wave_amplitude)
                        
                    else: # "combined"
                        wave_input = (start_y / canvas_height) * math.pi * 2 * wave_frequency
                        # Horizontal offsets shift on a sine curve, vertical offsets shift on a cosine curve
                        dest_x = int(math.sin(wave_input) * wave_amplitude)
                        dest_y = start_y + int(math.cos(wave_input) * (wave_amplitude // 2))
                    
                    # 4. Execute data paste and drop selection home
                    pasted_layers = Gimp.edit_paste(drawable, False)
                    if pasted_layers and len(pasted_layers) > 0:
                        floating_sel = pasted_layers[0]
                        floating_sel.set_offsets(dest_x, dest_y)
                        Gimp.floating_sel_anchor(floating_sel)

        except Exception as err:
            error_msg = "".join(traceback.format_exception(type(err), err, err.__traceback__))
            Gimp.message(f"Quantum Channel Slip Error:\n{error_msg}")
            
        finally:
            if original_channels:
                for channel, state in original_channels.items():
                    image.set_component_active(channel, state)

            image.select_rectangle(Gimp.ChannelOps.REPLACE, 0, 0, 0, 0)
            Gimp.context_pop()
            image.undo_group_end()

        Gimp.displays_flush()

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

Gimp.main(QuantumChannelSlip.__gtype__, sys.argv)