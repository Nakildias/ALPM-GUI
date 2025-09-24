import customtkinter as ctk
import subprocess
import threading
import re
import os
import json
import io
from tkinter import messagebox
from PIL import Image
from typing import Callable, Optional, Any
import math

# --- Try to import cairosvg, guide user if missing ---
try:
    import cairosvg
except ImportError:
    print("ERROR: CairoSVG library not found.")
    print("Please install it by running: pip install cairosvg")
    exit()

from customtkinter.windows.widgets.theme import ThemeManager

# --- Configuration -----------------------------------------------------------

class Config:
    """Stores application-wide configuration and constants."""
    GEOMETRY: str = "1200x850"
    TITLE: str = "Arch Linux Package Manager"
    CACHE_DIR: str = os.path.expanduser("~/.cache/apm_cache")
    ITEMS_PER_PAGE: int = 50
    ICON_SIZE: tuple[int, int] = (20, 20)

    # Modes
    MODE_SYSTEM: str = "System"
    MODE_FLATPAK: str = "Flatpak"

    # Sources
    SOURCE_PACMAN: str = "pacman"
    SOURCE_YAY: str = "yay"
    SOURCE_FLATPAK: str = "flatpak"

# --- SVG Icon Data -----------------------------------------------------------

class Icons:
    """Stores SVG data for all application icons."""
    # Icons sourced from feathericons.com (MIT License)
    SEARCH = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>'
    REFRESH = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>'
    LAYERS = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>'
    UPDATE = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"></path><polyline points="16 12 12 8 8 12"></polyline><line x1="12" y1="16" x2="12" y2="8"></line></svg>'
    INFO = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
    PLUS_CIRCLE = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg>'
    MINUS_CIRCLE = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="8" y1="12" x2="16" y2="12"></line></svg>'
    TRASH = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>'

# --- Utility Classes & Functions ---------------------------------------------

class IconFactory:
    """Creates and caches theme-aware CTkImage objects from SVG data."""
    _cache = {}

    @staticmethod
    def create(svg_data: str, size: tuple[int, int] = Config.ICON_SIZE) -> ctk.CTkImage:
        light_color = ThemeManager.theme["CTkLabel"]["text_color"][0]
        dark_color = ThemeManager.theme["CTkLabel"]["text_color"][1]

        cache_key = (svg_data, size, light_color, dark_color)
        if cache_key in IconFactory._cache:
            return IconFactory._cache[cache_key]

        light_image = IconFactory._render(svg_data, size, light_color)
        dark_image = IconFactory._render(svg_data, size, dark_color)

        ctk_image = ctk.CTkImage(light_image=light_image, dark_image=dark_image, size=size)
        IconFactory._cache[cache_key] = ctk_image
        return ctk_image

    @staticmethod
    def _render(svg_data: str, size: tuple[int, int], color: str) -> Image.Image:
        """Renders an SVG string into a PIL Image object with a specified color."""
        colored_svg = svg_data.replace('currentColor', color)
        png_bytes = cairosvg.svg2png(
            bytestring=colored_svg.encode('utf-8'),
            output_width=size[0],
            output_height=size[1]
        )
        return Image.open(io.BytesIO(png_bytes))

class CommandRunner:
    """Handles running shell commands in a separate thread with caching."""
    def __init__(self, app: 'App'):
        self.app = app
        if not os.path.exists(Config.CACHE_DIR):
            os.makedirs(Config.CACHE_DIR)

    def run(self, command: list[str], callback: Optional[Callable] = None, log_callback: Optional[Callable] = None, source: Optional[str] = None, cache_key: Optional[str] = None, force_refresh: bool = False, requires_sudo: bool = False, set_global_busy: bool = True):
        thread = threading.Thread(
            target=self._execute,
            args=(command, callback, log_callback, source, cache_key, force_refresh, requires_sudo, set_global_busy),
            daemon=True
        )
        thread.start()

    def _execute(self, command: list[str], callback: Optional[Callable], log_callback: Optional[Callable], source: Optional[str], cache_key: Optional[str], force_refresh: bool, requires_sudo: bool, set_global_busy: bool):
        if set_global_busy:
            self.app.after(0, self.app.set_busy, True)

        output_str: Optional[str] = None
        cache_path = os.path.join(Config.CACHE_DIR, cache_key) if cache_key else None

        password = None
        if requires_sudo:
            password_event = threading.Event()
            password_ref = [None]

            def get_password():
                # FIX: Pass the main app window (self.app) as the master to the dialog.
                pwd = PasswordDialog(self.app, text="Enter administrator password:", title="Authentication Required").get_input()
                password_ref[0] = pwd
                password_event.set()

            self.app.after(0, get_password)
            password_event.wait()
            password = password_ref[0]

            if not password:
                log_msg = "Sudo command cancelled: No password provided."
                self.app.after(0, self.app.log_to_console, log_msg)
                if log_callback: self.app.after(0, log_callback, log_msg + "\n")
                if set_global_busy: self.app.after(0, self.app.set_busy, False)
                # Still call the final callback so the chain doesn't break
                if callback: self.app.after(0, callback, "", source)
                return

            command = ["sudo", "-S"] + command

        if cache_path and os.path.exists(cache_path) and not force_refresh:
            with open(cache_path, 'r', encoding='utf-8') as f:
                output_str = f.read()
            # If there's a log callback, send the cached content to it
            if log_callback: self.app.after(0, log_callback, output_str)
            self.app.after(0, self.app.update_status, "Ready (from cache)")
        else:
            cmd_str = ' '.join(command)
            self.app.after(0, self.app.update_status, f"Running: {cmd_str}")
            self.app.after(0, self.app.log_to_console, f"Running: {cmd_str}")

            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, # Merge stderr with stdout
                    stdin=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace', # Prevent encoding errors from crashing
                    bufsize=1 # Line-buffered
                )

                # Write password to stdin if required, then close it
                if password and process.stdin:
                    try:
                        process.stdin.write(f"{password}\n")
                        process.stdin.flush()
                    except (IOError, BrokenPipeError):
                        # Handle cases where the process closes stdin early
                        pass

                full_output = []
                # Read stdout line by line in real-time
                if process.stdout:
                    for line in iter(process.stdout.readline, ''):
                        full_output.append(line)
                        if log_callback:
                            self.app.after(0, log_callback, line)
                    process.stdout.close()

                process.wait() # Wait for the process to terminate
                output_str = "".join(full_output)

                # Check for specific errors in the captured output
                if process.returncode != 0 and "incorrect password" in output_str:
                    self.app.after(0, self.app.log_to_console, "Error: Incorrect password for sudo.")
                    self.app.after(0, lambda: messagebox.showerror("Authentication Failed", "The password you entered was incorrect."))
                elif process.returncode != 0:
                    self.app.after(0, self.app.log_to_console, f"Process exited with code {process.returncode}")

                # Cache the result if successful
                if cache_path and output_str.strip():
                    with open(cache_path, 'w', encoding='utf-8') as f:
                        f.write(output_str)

            except FileNotFoundError:
                msg = f"Error: Command not found - {command[0]}."
                self.app.after(0, self.app.log_to_console, msg)
                self.app.after(0, lambda: messagebox.showerror("Command Not Found", msg))
            except Exception as e:
                 msg = f"An unexpected error occurred: {e}"
                 self.app.after(0, self.app.log_to_console, msg)
                 if log_callback: self.app.after(0, log_callback, msg + "\n")


            self.app.after(0, self.app.update_status, "Ready")

        if callback and output_str is not None:
            self.app.after(0, lambda: callback(output_str, source))

        if set_global_busy:
            self.app.after(0, self.app.set_busy, False)


# --- UI Components -----------------------------------------------------------

class Sidebar(ctk.CTkFrame):
    """The left-hand sidebar for controls and actions."""
    def __init__(self, master: 'App'):
        super().__init__(master, width=250)
        self.master = master
        self.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsw")

        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(pady=(20, 10), padx=10, fill="x")

        line1 = ctk.CTkLabel(title_frame, text="Arch Linux", font=ctk.CTkFont(size=22, weight="bold"))
        line1.pack()

        line2 = ctk.CTkLabel(title_frame, text="GUI Package Manager", font=ctk.CTkFont(size=16))
        line2.pack(pady=(0, 0))

        # Create a new frame to ensure right alignment
        author_frame = ctk.CTkFrame(title_frame, fg_color="transparent")
        author_frame.pack(fill="x")

        line3 = ctk.CTkLabel(author_frame, text="Version: 1.0     |     by Nakildias", font=ctk.CTkFont(size=10), text_color="gray50")
        line3.pack(side="top")

        self.mode_selector = ctk.CTkSegmentedButton(self, values=[Config.MODE_SYSTEM, Config.MODE_FLATPAK], command=master.switch_mode)
        self.mode_selector.pack(fill="x", padx=10, pady=10)
        self.mode_selector.set(Config.MODE_SYSTEM)


        ctk.CTkFrame(self, height=2, fg_color="gray").pack(fill="x", padx=10, pady=10)

        self.refresh_button = ctk.CTkButton(self, text="Refresh Lists", image=IconFactory.create(Icons.REFRESH), anchor="w", command=lambda: master.refresh_installed_list(force=True))
        self.refresh_button.pack(fill="x", padx=10, pady=5)

        self.queue_button = ctk.CTkButton(self, text="Show Queue (0)", image=IconFactory.create(Icons.LAYERS), anchor="w", command=master.show_queue_window)
        self.queue_button.pack(fill="x", padx=10, pady=5)

        self.update_button = ctk.CTkButton(self, text="Update System", image=IconFactory.create(Icons.UPDATE), anchor="w", command=master.show_update_confirmation)
        self.update_button.pack(fill="x", padx=10, pady=5)

        self.aur_switch = ctk.CTkSwitch(self, text="Enable AUR (yay)", variable=master.aur_enabled)
        self.aur_switch.pack(anchor="w", padx=20, pady=10)

    def get_widgets_to_disable(self):
        return [self.mode_selector, self.aur_switch, self.refresh_button, self.queue_button, self.update_button]

class MainContent(ctk.CTkFrame):
    """The main content area with search and tabs."""
    def __init__(self, master: 'App'):
        super().__init__(master, fg_color="transparent")
        self.master = master
        self.grid(row=0, column=1, rowspan=2, padx=10, pady=10, sticky="nsew")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        search_frame = ctk.CTkFrame(self)
        search_frame.grid(row=0, column=0, sticky="new", pady=(0, 10))
        search_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search for packages...")
        self.search_entry.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.search_entry.bind("<Return>", master.search_packages_event)

        self.search_button = ctk.CTkButton(search_frame, text="", image=IconFactory.create(Icons.SEARCH), width=40, command=master.search_packages_event)
        self.search_button.grid(row=0, column=1, padx=(0, 10), pady=10)

        self.tab_view = ctk.CTkTabview(self, command=master.on_tab_change)
        self.tab_view.grid(row=1, column=0, sticky="nsew")
        self.tab_view.add("Search Results")
        self.tab_view.add("Installed")
        self.tab_view.add("Groups")
        self.tab_view.add("Console")

        self._create_tab_content()

    def _create_tab_content(self):
        # Search Tab
        search_tab = self.tab_view.tab("Search Results")
        search_tab.grid_rowconfigure(0, weight=1)
        search_tab.grid_columnconfigure(0, weight=1)
        self.search_results_frame = ctk.CTkScrollableFrame(search_tab)
        self.search_results_frame.grid(row=0, column=0, sticky="nsew")
        self.search_pagination_frame = ctk.CTkFrame(search_tab, height=40)
        self.search_pagination_frame.grid(row=1, column=0, sticky="ew", pady=(5,0))
        self._create_pagination_controls('search')
        # Installed Tab
        installed_tab = self.tab_view.tab("Installed")
        installed_tab.grid_rowconfigure(0, weight=1)
        installed_tab.grid_columnconfigure(0, weight=1)
        self.installed_frame = ctk.CTkScrollableFrame(installed_tab)
        self.installed_frame.grid(row=0, column=0, sticky="nsew")
        self.installed_pagination_frame = ctk.CTkFrame(installed_tab, height=40)
        self.installed_pagination_frame.grid(row=1, column=0, sticky="ew", pady=(5,0))
        self._create_pagination_controls('installed')
        # Groups Tab
        groups_tab = self.tab_view.tab("Groups")
        groups_tab.grid_rowconfigure(0, weight=1)
        groups_tab.grid_columnconfigure(0, weight=1)
        self.groups_frame = ctk.CTkScrollableFrame(groups_tab)
        self.groups_frame.grid(row=0, column=0, sticky="nsew")
        # Console Tab
        console_tab = self.tab_view.tab("Console")
        console_tab.grid_rowconfigure(0, weight=1)
        console_tab.grid_columnconfigure(0, weight=1)
        self.console_text = ctk.CTkTextbox(console_tab, state="disabled")
        self.console_text.grid(row=0, column=0, sticky="nsew")

    def _create_pagination_controls(self, view_type: str):
        """Creates the pagination widgets once to prevent flickering."""
        if view_type == 'search':
            pagination_frame = self.search_pagination_frame
        else:
            pagination_frame = self.installed_pagination_frame

        controls_container = ctk.CTkFrame(pagination_frame, fg_color="transparent")
        controls_container.pack(expand=True)

        prev_button = ctk.CTkButton(controls_container, text="<< Prev", command=lambda: self.master.change_page(view_type, -1))
        prev_button.pack(side="left", padx=10, pady=5)

        page_label = ctk.CTkLabel(controls_container, text="")
        page_label.pack(side="left", padx=10, pady=5)

        next_button = ctk.CTkButton(controls_container, text="Next >>", command=lambda: self.master.change_page(view_type, 1))
        next_button.pack(side="left", padx=10, pady=5)

        if view_type == 'search':
            self.search_pagination_container = controls_container
            self.search_prev_btn = prev_button
            self.search_page_label = page_label
            self.search_next_btn = next_button
        else:
            self.installed_pagination_container = controls_container
            self.installed_prev_btn = prev_button
            self.installed_page_label = page_label
            self.installed_next_btn = next_button

        controls_container.pack_forget() # Hide by default

    def get_widgets_to_disable(self):
        return [self.search_entry, self.search_button]

# --- Dialog Windows ----------------------------------------------------------

class ProcessDialog(ctk.CTkToplevel):
    """A dialog to show real-time output and progress for a command."""
    def __init__(self, master: 'App', title: str):
        super().__init__(master)
        self.title(title)
        self.geometry("800x600")
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._on_close_attempt)
        self.after(20, self.grab_set)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.textbox = ctk.CTkTextbox(self, state="disabled", wrap="word")
        self.textbox.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.progress_bar = ctk.CTkProgressBar(self, mode="indeterminate")
        self.progress_bar.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="ew")
        self.progress_bar.start()

        self.close_button = ctk.CTkButton(self, text="Close", state="disabled", command=self.destroy)
        self.close_button.grid(row=2, column=0, padx=10, pady=(5, 10))

    def append_log(self, text: str):
        if self.winfo_exists():
            self.textbox.configure(state="normal")
            self.textbox.insert("end", text)
            self.textbox.configure(state="disabled")
            self.textbox.see("end")

    def on_complete(self):
        if self.winfo_exists():
            self.progress_bar.stop()
            self.progress_bar.set(1)
            self.close_button.configure(state="normal")
            self.master.bell() # Notify user

    def _on_close_attempt(self):
        # Prevent closing while process is running
        if self.close_button.cget("state") == "disabled":
            messagebox.showwarning("In Progress", "A process is still running. Please wait for it to complete.", parent=self)
        else:
            self.destroy()


class PasswordDialog(ctk.CTkToplevel):
    """A custom Toplevel dialog to get a password, fixing the inheritance issue."""
    # FIX: Add 'master' as the first argument to the constructor.
    def __init__(self, master, title: str, text: str):
        # FIX: Pass 'master' to the superclass constructor.
        super().__init__(master)

        self.title(title)
        # FIX: Use the 'master' variable for the transient call.
        self.transient(master)
        self.after(20, self.grab_set)
        self.protocol("WM_DELETE_WINDOW", self._cancel_event)

        self.result = None

        ctk.CTkLabel(self, text=text).pack(padx=20, pady=(20, 10))
        self.entry = ctk.CTkEntry(self, show="*")
        self.entry.pack(padx=20, pady=(0, 10), fill="x")
        self.entry.bind("<Return>", self._ok_event)

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(padx=20, pady=(0, 20), fill="x")
        button_frame.grid_columnconfigure((0, 1), weight=1)

        ok_button = ctk.CTkButton(button_frame, text="OK", command=self._ok_event)
        ok_button.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self._cancel_event)
        cancel_button.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        self.after(10, self._center_window)
        self.entry.focus_set()

    def _ok_event(self, event=None):
        self.result = self.entry.get()
        self.destroy()

    def _cancel_event(self, event=None):
        self.result = None
        self.destroy()

    def _center_window(self):
        self.update_idletasks()
        x = self.winfo_screenwidth() // 2 - self.winfo_width() // 2
        y = self.winfo_screenheight() // 2 - self.winfo_height() // 2
        self.geometry(f"+{x}+{y}")

    def get_input(self):
        self.wait_window()
        return self.result

class MessageDialog(ctk.CTkToplevel):
    """A custom dialog to show an informational message with app styling."""
    def __init__(self, title: str, message: str):
        super().__init__()
        self.title(title)
        self.transient(self.master)
        self.after(20, self.grab_set)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.resizable(False, False)
        ctk.CTkLabel(self, text=message, wraplength=350, justify="left").pack(padx=20, pady=(20, 10))
        ok_button = ctk.CTkButton(self, text="OK", command=self.destroy, width=100)
        ok_button.pack(padx=20, pady=(10, 20))
        self.after(10, self._center_window)
        ok_button.focus_set()
        ok_button.bind("<Return>", lambda e: self.destroy())

    def _center_window(self):
        self.update_idletasks()
        x = self.winfo_screenwidth() // 2 - self.winfo_width() // 2
        y = self.winfo_screenheight() // 2 - self.winfo_height() // 2
        self.geometry(f"+{x}+{y}")

class InfoDialog(ctk.CTkToplevel):
    """Dialog to display package information."""
    def __init__(self, master: 'App', pkg: dict):
        super().__init__(master)
        self.master_app = master
        self.pkg_data = pkg
        self.pkg_name = pkg['name']
        self.source = pkg['source']

        self.title(f"Info: {self.pkg_name}")
        self.geometry("600x500")
        self.transient(master)
        self.after(20, self.grab_set)

        ctk.CTkLabel(self, text="Package Information", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        # Create a container frame that will hold either the textbox or the structured view
        self.info_container = ctk.CTkFrame(self, fg_color="transparent")
        self.info_container.pack(expand=True, fill="both", padx=10, pady=10)

        # Display a loading message initially
        self.loading_label = ctk.CTkLabel(self.info_container, text=f"Loading info for {self.pkg_name}...")
        self.loading_label.pack(pady=20)

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(side="bottom", fill="x", padx=10, pady=10)
        button_frame.grid_columnconfigure((0, 1), weight=1)

        is_installed = self.pkg_name in self.master_app.installed_packages
        is_queued = self.master_app.is_in_queue(self.pkg_name) is not None

        if is_queued:
            btn_text, btn_icon, action_command = "Remove from Queue", IconFactory.create(Icons.TRASH), self.remove_from_queue
        elif is_installed:
            btn_text, btn_icon, action_command = "Uninstall", IconFactory.create(Icons.MINUS_CIRCLE), lambda: self.add_to_queue("remove")
        else:
            btn_text, btn_icon, action_command = "Install", IconFactory.create(Icons.PLUS_CIRCLE), lambda: self.add_to_queue("install")

        action_button = ctk.CTkButton(button_frame, text=btn_text, image=btn_icon, command=action_command)
        action_button.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        ctk.CTkButton(button_frame, text="Close", command=self.destroy).grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # FIX: Use 'remote-info' for uninstalled flatpaks and 'info' for installed ones.
        cmd = []
        if self.source == Config.SOURCE_FLATPAK:
            if is_installed:
                # Use 'flatpak info' for installed packages
                cmd = ["flatpak", "info", self.pkg_name]
            else:
                # Use 'flatpak remote-info' for packages from search results (not installed)
                remote = self.pkg_data.get('remote')
                if remote:
                    cmd = ["flatpak", "remote-info", remote, self.pkg_name]
                else:
                    # Handle case where an uninstalled app has no remote info
                    self.after(10, lambda: self.update_info("Cannot fetch info: remote not specified.", None))
        else:  # Catches SOURCE_YAY and SOURCE_PACMAN
            cmd = ["yay", "-Si", self.pkg_name]

        if cmd:  # Only run if a command was successfully constructed
            self.master_app.command_runner.run(cmd, self.update_info, cache_key=f"info_{self.pkg_name}.cache")


    def update_info(self, output: str, source: Optional[str]):
        if not self.winfo_exists(): return

        # Clear the loading message
        self.loading_label.destroy()

        # Check the source of the package to determine display format
        if self.source == Config.SOURCE_FLATPAK:
            self._parse_and_display_flatpak_info(output)
        else: # Covers pacman and yay
            self._parse_and_display_system_info(output)

    def _update_wraplengths(self, event):
        """Dynamically update wraplength of value labels based on frame width."""
        # Estimate key column width.
        key_col_width = 140
        # Calculate available width for the value column and full-width labels.
        value_wraplength = event.width - key_col_width - 40  # Subtract key width and padding
        full_wraplength = event.width - 20 # Subtract padding

        # Enforce a minimum width to prevent labels from collapsing.
        if value_wraplength < 100: value_wraplength = 100
        if full_wraplength < 100: full_wraplength = 100

        # Update labels based on whether they span the full width.
        for label, is_full in self.labels_to_wrap:
            if is_full:
                label.configure(wraplength=full_wraplength)
            else:
                label.configure(wraplength=value_wraplength)

    def _parse_and_display_system_info(self, output: str):
        """Parses system package info and displays it in a structured way."""
        scroll_frame = ctk.CTkScrollableFrame(self.info_container)
        scroll_frame.pack(expand=True, fill="both")
        scroll_frame.grid_columnconfigure(1, weight=1)

        self.labels_to_wrap = []
        row_counter = 0
        # Regex for key-value pairs separated by a colon, handling multi-line values
        pattern = re.compile(r"^([\w\s-]+?)\s*:\s*(.*?)(?=\n^[\w\s-]+?\s*:|$)", re.DOTALL | re.MULTILINE)

        match_list = list(pattern.finditer(output))

        if not match_list:
            # Fallback for when no key-value pairs are found
            fallback_label = ctk.CTkLabel(scroll_frame, text=output, justify="left")
            fallback_label.pack(padx=10, pady=10)
            self.labels_to_wrap.append((fallback_label, True))
        else:
            for match in match_list:
                key, value = match.group(1).strip(), match.group(2).strip()
                if not value: continue # Skip empty values like 'Groups: None' if parsed as empty

                key_label = ctk.CTkLabel(scroll_frame, text=key, font=ctk.CTkFont(weight="bold"))
                key_label.grid(row=row_counter, column=0, sticky="nw", padx=10, pady=5)

                val_label = ctk.CTkLabel(scroll_frame, text=value, justify="left")
                val_label.grid(row=row_counter, column=1, sticky="nw", padx=10, pady=5)
                self.labels_to_wrap.append((val_label, False))
                row_counter += 1

        scroll_frame.bind("<Configure>", self._update_wraplengths, add='+')
        self._bind_scrolling_recursive(scroll_frame, scroll_frame)


    def _parse_and_display_flatpak_info(self, output: str):
        """Parses flatpak info and displays it in a structured, wrappable way, ignoring the header description."""
        scroll_frame = ctk.CTkScrollableFrame(self.info_container)
        scroll_frame.pack(expand=True, fill="both")
        scroll_frame.grid_columnconfigure(1, weight=1)

        self.labels_to_wrap = []
        row_counter = 0
        # More robust pattern to include characters like '.' and '()' in keys
        pattern = re.compile(r"^([\w\s().]+?):\s*(.*?)(?=\n^[\w\s().]+:|$)", re.DOTALL | re.MULTILINE)

        match_list = list(pattern.finditer(output))

        if not match_list:
            # Fallback for when no key-value pairs are found (e.g., error messages)
            fallback_label = ctk.CTkLabel(scroll_frame, text=output, justify="left")
            fallback_label.pack(padx=10, pady=10)
            self.labels_to_wrap.append((fallback_label, True))
        else:
            # Display key-value pairs, ignoring any text before the first match
            for match in match_list:
                key, value = match.group(1).strip(), match.group(2).strip()

                key_label = ctk.CTkLabel(scroll_frame, text=key, font=ctk.CTkFont(weight="bold"))
                key_label.grid(row=row_counter, column=0, sticky="nw", padx=10, pady=5)

                val_label = ctk.CTkLabel(scroll_frame, text=value, justify="left")
                val_label.grid(row=row_counter, column=1, sticky="nw", padx=10, pady=5)
                self.labels_to_wrap.append((val_label, False))
                row_counter += 1

        scroll_frame.bind("<Configure>", self._update_wraplengths, add='+')
        self._bind_scrolling_recursive(scroll_frame, scroll_frame)


    def _bind_scrolling_recursive(self, widget_to_bind, scroll_frame_to_scroll):
        """Recursively binds mouse wheel events to a widget and its children with boundary checks."""
        canvas = scroll_frame_to_scroll._parent_canvas

        def on_mousewheel(event):
            first, last = canvas.yview()
            # Scroll up
            if event.delta > 0 and first > 0.0:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            # Scroll down
            elif event.delta < 0 and last < 1.0:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def on_scroll_up(event):
            if canvas.yview()[0] > 0.0:
                canvas.yview_scroll(-1, "units")

        def on_scroll_down(event):
            if canvas.yview()[1] < 1.0:
                canvas.yview_scroll(1, "units")

        widget_to_bind.bind("<MouseWheel>", on_mousewheel, add='+')
        widget_to_bind.bind("<Button-4>", on_scroll_up, add='+')
        widget_to_bind.bind("<Button-5>", on_scroll_down, add='+')
        for child in widget_to_bind.winfo_children():
            self._bind_scrolling_recursive(child, scroll_frame_to_scroll)


    def add_to_queue(self, action: str):
        self.master_app.add_to_queue(action, self.pkg_name, self.source)
        self.destroy()

    def remove_from_queue(self):
        self.master_app.remove_from_queue(self.pkg_name)
        self.destroy()

class QueueDialog(ctk.CTkToplevel):
    """Dialog to display and manage the package queue."""
    def __init__(self, master: 'App'):
        super().__init__(master)
        self.master_app = master
        self.title("Package Queue")
        self.geometry("500x600")
        self.transient(master)
        self.after(20, self.grab_set)

        ctk.CTkLabel(self, text="Pending Operations", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        self.queue_frame = ctk.CTkScrollableFrame(self)
        self.queue_frame.pack(expand=True, fill="both", padx=10, pady=10)
        self.populate_queue_list()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        btn_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.proc_btn = ctk.CTkButton(btn_frame, text="Process Queue", command=self.process_queue)
        self.proc_btn.grid(row=0, column=0, padx=5, sticky="ew")
        self.clr_btn = ctk.CTkButton(btn_frame, text="Clear Queue", command=self.clear_queue)
        self.clr_btn.grid(row=0, column=1, padx=5, sticky="ew")
        ctk.CTkButton(btn_frame, text="Close", command=self.destroy).grid(row=0, column=2, padx=5, sticky="ew")

        if not self.master_app.package_queue:
            self.proc_btn.configure(state="disabled")
            self.clr_btn.configure(state="disabled")

    def populate_queue_list(self):
        for widget in self.queue_frame.winfo_children(): widget.destroy()
        if not self.master_app.package_queue:
            ctk.CTkLabel(self.queue_frame, text="The queue is empty.").pack(pady=20)
        else:
            for item in self.master_app.package_queue:
                action, color = ("INSTALL", "green") if item['action'] == 'install' else ("REMOVE", "red")
                item_frame = ctk.CTkFrame(self.queue_frame, fg_color="transparent")
                item_frame.pack(fill="x", pady=2)
                item_frame.grid_columnconfigure(0, weight=1)
                label = ctk.CTkLabel(item_frame, text=f"{action}: {item['pkg_name']} [{item['source']}]", text_color=color)
                label.grid(row=0, column=0, sticky="w", padx=5)
                remove_btn = ctk.CTkButton(item_frame, text="", image=IconFactory.create(Icons.TRASH), width=28, height=28, command=lambda pkg=item['pkg_name']: self.remove_item(pkg))
                remove_btn.grid(row=0, column=1, padx=5)

    def process_queue(self): self.master_app.process_queue(); self.destroy()
    def clear_queue(self):
        self.master_app.clear_queue(); self.populate_queue_list()
        self.proc_btn.configure(state="disabled"); self.clr_btn.configure(state="disabled")
    def remove_item(self, pkg_name: str):
        self.master_app.remove_from_queue(pkg_name); self.populate_queue_list()
        if not self.master_app.package_queue:
            self.proc_btn.configure(state="disabled"); self.clr_btn.configure(state="disabled")

class UpdateConfirmationDialog(ctk.CTkToplevel):
    """NEW: Dialog to show packages that will be upgraded."""
    def __init__(self, master: 'App', packages_to_update: list[str], confirm_callback: Callable):
        super().__init__(master)
        self.master_app = master
        self.confirm_callback = confirm_callback

        self.title("Update Confirmation")
        self.geometry("600x500")
        self.transient(master)
        self.after(20, self.grab_set)

        label_text = f"Found {len(packages_to_update)} packages to update. Confirm?"
        ctk.CTkLabel(self, text=label_text, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        scroll_frame = ctk.CTkScrollableFrame(self)
        scroll_frame.pack(expand=True, fill="both", padx=10, pady=10)

        for pkg in packages_to_update:
            ctk.CTkLabel(scroll_frame, text=pkg).pack(anchor="w", padx=5)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(btn_frame, text="Confirm Update", command=self.on_confirm).grid(row=0, column=0, sticky="ew", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy).grid(row=0, column=1, sticky="ew", padx=5)

    def on_confirm(self):
        self.confirm_callback()
        self.destroy()

# --- Main Application --------------------------------------------------------

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(Config.TITLE)
        self.geometry(Config.GEOMETRY)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.current_mode = Config.MODE_SYSTEM
        self.aur_enabled = ctk.BooleanVar(value=True)
        self.package_queue: list[dict] = []
        self.installed_packages: set[str] = set()
        self.upgradable_packages: set[str] = set()
        self.search_results_data: list[dict] = []
        self.installed_packages_data: list[dict] = []
        self.full_installed_packages_data: list[dict] = []
        self.search_page: int = 1
        self.installed_page: int = 1

        self.command_runner = CommandRunner(self)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.sidebar = Sidebar(self)
        self.main_content = MainContent(self)

        self.status_bar = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.status_bar.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        self.widgets_to_disable_during_task = (
            self.sidebar.get_widgets_to_disable() +
            self.main_content.get_widgets_to_disable()
        )
        self.after(100, self.initial_load)

        # --- Global Scroll Bindings ---
        self.bind("<MouseWheel>", self._on_global_mousewheel, add='+')
        self.bind("<Button-4>", self._on_global_scroll_up, add='+')
        self.bind("<Button-5>", self._on_global_scroll_down, add='+')

    def _is_widget_descendant(self, widget, master) -> bool:
        """Helper to check if a widget is a descendant of a master widget."""
        if widget is None: return False
        parent = widget
        while parent is not None:
            if parent == master: return True
            parent = parent.master
        return False

    def _get_active_scrollable_frame(self) -> Optional[ctk.CTkScrollableFrame]:
        """Gets the currently visible scrollable frame based on the active tab."""
        current_tab = self.main_content.tab_view.get()
        if current_tab == "Search Results": return self.main_content.search_results_frame
        elif current_tab == "Installed": return self.main_content.installed_frame
        elif current_tab == "Groups": return self.main_content.groups_frame
        return None

    def _on_global_mousewheel(self, event):
        frame = self._get_active_scrollable_frame()
        if frame:
            widget_under_mouse = self.winfo_containing(event.x_root, event.y_root)
            if self._is_widget_descendant(widget_under_mouse, frame):
                canvas = frame._parent_canvas
                first, last = canvas.yview()
                # Scroll up
                if event.delta > 0 and first > 0.0:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                # Scroll down
                elif event.delta < 0 and last < 1.0:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_global_scroll_up(self, event):
        frame = self._get_active_scrollable_frame()
        if frame:
            widget_under_mouse = self.winfo_containing(event.x_root, event.y_root)
            if self._is_widget_descendant(widget_under_mouse, frame):
                canvas = frame._parent_canvas
                if canvas.yview()[0] > 0.0:
                    canvas.yview_scroll(-1, "units")

    def _on_global_scroll_down(self, event):
        frame = self._get_active_scrollable_frame()
        if frame:
            widget_under_mouse = self.winfo_containing(event.x_root, event.y_root)
            if self._is_widget_descendant(widget_under_mouse, frame):
                canvas = frame._parent_canvas
                if canvas.yview()[1] < 1.0:
                    canvas.yview_scroll(1, "units")

    def initial_load(self):
        self.refresh_installed_list()
        self.populate_groups()

    def set_busy(self, is_busy: bool):
        state = "disabled" if is_busy else "normal"
        for widget in self.widgets_to_disable_during_task:
            widget.configure(state=state)
        self.update_idletasks()

    def update_status(self, text: str): self.status_bar.configure(text=text)
    def log_to_console(self, message: str):
        self.main_content.console_text.configure(state="normal")
        self.main_content.console_text.insert("end", message + "\n")
        self.main_content.console_text.configure(state="disabled")
        self.main_content.console_text.see("end")

    def switch_mode(self, new_mode: str):
        self.current_mode = new_mode
        self.main_content.search_entry.delete(0, "end")
        self.search_results_data.clear()
        self.update_page_view('search') # Clear the visual search results
        is_system = self.current_mode == Config.MODE_SYSTEM
        self.sidebar.update_button.configure(text="Update System" if is_system else "Update Flatpak")
        self.sidebar.aur_switch.pack(anchor="w", padx=20, pady=10) if is_system else self.sidebar.aur_switch.pack_forget()
        try:
            # FIX: CTkTabview does not have .values(). Use internal ._name_list to get tab names.
            tab_names = self.main_content.tab_view._name_list
            if is_system and "Groups" not in tab_names:
                self.main_content.tab_view.add("Groups")
                self.populate_groups()
            elif not is_system and "Groups" in tab_names:
                # Before deleting the tab, make sure it's not the active one
                if self.main_content.tab_view.get() == "Groups":
                    self.main_content.tab_view.set("Installed") # Switch to a default tab
                self.main_content.tab_view.delete("Groups")
        except (RuntimeError, ValueError): pass
        self.on_tab_change()
        self.refresh_installed_list()

    def refresh_installed_list(self, force: bool = False):
        self.installed_packages.clear(); self.upgradable_packages.clear()
        if self.current_mode == Config.MODE_SYSTEM:
            cmd, source = ["pacman", "-Q"], Config.SOURCE_PACMAN
            self.command_runner.run(["yay", "-Qu"], self._parse_upgradable_system, force_refresh=True)
        else:
            cmd, source = ["flatpak", "list", "--app", "--columns=name,application,version,branch,installation,size"], Config.SOURCE_FLATPAK
            self.command_runner.run(["flatpak", "remote-ls", "--updates"], self._parse_upgradable_flatpak, force_refresh=True)
        # FIX: Switched to keyword arguments to prevent misaligned parameters.
        self.command_runner.run(cmd, callback=self.parse_and_display_installed, source=source, cache_key=f"installed_{source}.cache", force_refresh=force)

    def search_packages_event(self, event: Optional[Any] = None):
        query = self.main_content.search_entry.get().strip()
        current_tab = self.main_content.tab_view.get()
        if current_tab == "Search Results":
            if not query: return
            self.search_results_data.clear()
            if self.current_mode == Config.MODE_SYSTEM:
                use_aur = self.aur_enabled.get()
                cmd, source = (["yay", "-Ss", query], Config.SOURCE_YAY) if use_aur else (["pacman", "-Ss", query], Config.SOURCE_PACMAN)
                # This call is already correct.
                self.command_runner.run(cmd, callback=self.parse_system_search, source=source, cache_key=f"{source}_{query.replace(' ', '_')}.cache")
            else:
                # FIX: Use keyword arguments to correctly pass the callback and source.
                self.command_runner.run(
                    ["flatpak", "remote-ls", "--app", "--columns=name,description,application,version,installed-size,origin"],
                    callback=self.parse_flatpak_search,
                    source=Config.SOURCE_FLATPAK
                )
        elif current_tab == "Installed":
            query_lower = query.lower()
            if not query_lower: self.installed_packages_data = self.full_installed_packages_data
            else: self.installed_packages_data = self._sort_results([pkg for pkg in self.full_installed_packages_data if query_lower in pkg['name'].lower()], query)
            self.installed_page = 1
            self.update_page_view('installed')

    def on_tab_change(self):
        current_tab = self.main_content.tab_view.get()
        placeholder = ""
        if current_tab == "Installed": placeholder = f"Filter installed {self.current_mode.lower()} packages..."
        elif current_tab == "Search Results": placeholder = "Search Pacman/AUR..." if self.current_mode == Config.MODE_SYSTEM else "Search Flatpak..."
        self.main_content.search_entry.delete(0, "end")
        self.main_content.search_entry.configure(placeholder_text=placeholder)
        self.focus()
        self.update_idletasks()
        if current_tab in ["Search Results", "Installed"]: self.after(250, self.main_content.search_entry.focus)

    def show_update_confirmation(self):
        """Fetches update list and shows confirmation dialog."""
        def on_list_fetched(output: str, source: Optional[str]):
            upgradable_list = sorted(list(self.upgradable_packages))
            if not upgradable_list:
                MessageDialog("Up to Date", f"All {self.current_mode} packages are up to date.")
                return

            def run_update():
                if self.current_mode == Config.MODE_SYSTEM:
                    # Use pacman -Syu for system updates as requested.
                    update_cmd = ["pacman", "-Syu", "--noconfirm"]
                else:
                    update_cmd = ["flatpak", "update", "-y", "--verbose"]

                dialog = ProcessDialog(self, f"Updating {self.current_mode}")

                def log_callback(line):
                    dialog.append_log(line)

                def completion_callback(output, source):
                    dialog.on_complete()
                    self.log_to_console(f"{self.current_mode} update process finished.")
                    self.refresh_installed_list(force=True)

                self.command_runner.run(
                    update_cmd,
                    callback=completion_callback,
                    log_callback=log_callback,
                    requires_sudo=(self.current_mode == Config.MODE_SYSTEM),
                    force_refresh=True,
                    set_global_busy=False
                )

            UpdateConfirmationDialog(self, upgradable_list, run_update)

        # Command to fetch the list of upgradable packages
        list_cmd = ["yay", "-Qu"] if self.current_mode == Config.MODE_SYSTEM else ["flatpak", "remote-ls", "--updates"]
        self.command_runner.run(list_cmd, on_list_fetched, force_refresh=True)

    def parse_and_display_installed(self, output: str, source: str):
        packages = []
        if source == Config.SOURCE_PACMAN:
            for line in output.strip().split('\n'):
                if line: name, version = line.split(); packages.append({"name": name, "version": version, "source": source})
        elif source == Config.SOURCE_FLATPAK:
            for line in output.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 6:
                    packages.append({"friendly_name": parts[0], "name": parts[1], "version": parts[2], "size": parts[5], "source": source})
        for pkg in packages:
            self.installed_packages.add(pkg['name']); pkg['is_installed'] = True
        self.full_installed_packages_data = sorted(packages, key=lambda p: p['name'].lower())
        self.installed_packages_data = self.full_installed_packages_data
        self.installed_page = 1
        self.update_page_view('installed')

    def parse_system_search(self, output: str, source: str):
        packages, lines, i = [], output.strip().split('\n'), 0
        while i < len(lines):
            header_line = lines[i]
            if "/" in header_line and not header_line.startswith(" "):
                desc_line = ""
                if i + 1 < len(lines) and lines[i+1].startswith("    "): desc_line = lines[i + 1].strip(); i += 1
                parts = header_line.split()
                if len(parts) >= 2:
                    repo_and_name, version = parts[0].split('/'), parts[1]
                    # FIX: Use source constants for system packages to avoid bugs
                    source_const = Config.SOURCE_YAY if 'aur' in repo_and_name[0] else Config.SOURCE_PACMAN
                    packages.append({"name": repo_and_name[1], "version": version, "desc": desc_line, "source": source_const})
            i += 1
        query = self.main_content.search_entry.get()
        self.search_results_data = self._sort_results(packages, query)
        self.search_page = 1; self.update_page_view('search')

    def parse_flatpak_search(self, output: str, source: Optional[str]):
        query = self.main_content.search_entry.get().lower()
        if not query: self.search_results_data = []; self.update_page_view('search'); return
        all_packages = []
        for line in output.strip().split('\n'):
            parts = line.split('\t')
            # Expect 6 columns now: name, description, application, version, installed-size, origin
            if len(parts) >= 6:
                size_formatted = parts[4].strip()
                if not size_formatted or size_formatted == "0": # Sometimes it outputs "0" for no size
                    size_formatted = "N/A"

                all_packages.append({
                    "friendly_name": parts[0],
                    "description": parts[1],
                    "app_id": parts[2],
                    "version": parts[3],
                    "size": size_formatted,
                    "remote": parts[5],
                    "name": parts[2].split('.')[-1]
                })
        filtered = [p for p in all_packages if query in p['name'].lower() or query in p['friendly_name'].lower() or query in p['app_id'].lower()]
        # Map the parsed data to the keys used by the display function
        final_results = [{
            'name': p['app_id'],
            'source': Config.SOURCE_FLATPAK,
            'display_name': p['friendly_name'],
            'version': p['version'],
            'desc': p['description'],
            'size': p['size'],
            'remote': p['remote'],
            'is_installed': p['app_id'] in self.installed_packages
        } for p in self._sort_results(filtered, query)]
        self.search_results_data = final_results; self.search_page = 1; self.update_page_view('search')

    def _sort_results(self, results: list[dict], query: str) -> list[dict]:
        query_lower = query.lower(); results.sort(key=lambda p: p.get('name', '').lower()); results.sort(key=lambda p: 0 if p.get('name', '').lower() == query_lower else 1); return results

    def update_page_view(self, view_type: str):
        if view_type == 'search':
            frame, data, page = self.main_content.search_results_frame, self.search_results_data, self.search_page
            pagination_container = self.main_content.search_pagination_container
            prev_btn, page_label, next_btn = self.main_content.search_prev_btn, self.main_content.search_page_label, self.main_content.search_next_btn
        else:
            frame, data, page = self.main_content.installed_frame, self.installed_packages_data, self.installed_page
            pagination_container = self.main_content.installed_pagination_container
            prev_btn, page_label, next_btn = self.main_content.installed_prev_btn, self.main_content.installed_page_label, self.main_content.installed_next_btn

        for widget in frame.winfo_children(): widget.destroy()

        if not data:
            ctk.CTkLabel(frame, text="No packages found.").pack(pady=20)
            pagination_container.pack_forget() # Hide pagination if no data
            return

        total_pages = (len(data) + Config.ITEMS_PER_PAGE - 1) // Config.ITEMS_PER_PAGE
        start = (page - 1) * Config.ITEMS_PER_PAGE
        end = start + Config.ITEMS_PER_PAGE

        for pkg in data[start:end]:
            item_frame = ctk.CTkFrame(frame, border_width=1)
            item_frame.pack(fill="x", pady=2, padx=5)

            if view_type == 'search':
                self._create_search_list_item(item_frame, pkg)
            else: # installed
                self._create_installed_list_item(item_frame, pkg)

        if total_pages > 1:
            pagination_container.pack(expand=True)
            page_label.configure(text=f"Page {page} of {total_pages}")
            prev_btn.configure(state="normal" if page > 1 else "disabled")
            next_btn.configure(state="normal" if page < total_pages else "disabled")
        else:
            pagination_container.pack_forget()

    def _add_hover_effect(self, widgets: list[ctk.CTkBaseClass]):
        """NEW: Adds hover effect to a list of widgets."""
        master_frame = widgets[0] # Assume the first widget is the main frame
        original_color = master_frame.cget("fg_color")
        hover_color = ThemeManager.theme["CTkButton"]["hover_color"]
        for widget in widgets:
            widget.bind("<Enter>", lambda e, f=master_frame, c=hover_color: f.configure(fg_color=c))
            widget.bind("<Leave>", lambda e, f=master_frame, c=original_color: f.configure(fg_color=c))

    def _create_search_list_item(self, master: ctk.CTkFrame, pkg: dict):
        master.grid_columnconfigure(0, weight=1)
        name_text, desc_text = (pkg.get('display_name', pkg.get('name')), pkg.get('desc', '')) if pkg.get('source') == Config.SOURCE_FLATPAK else (pkg.get('name'), pkg.get('desc', ''))
        top_frame = ctk.CTkFrame(master, fg_color="transparent"); top_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5,0))
        name_label = ctk.CTkLabel(top_frame, text=name_text, font=ctk.CTkFont(weight="bold")); name_label.pack(side="left")
        source_label = ctk.CTkLabel(top_frame, text=f"({pkg.get('source', 'N/A')})", text_color="gray"); source_label.pack(side="left", padx=5)
        desc_label = ctk.CTkLabel(master, text=desc_text, wraplength=master.winfo_width()-20, justify="left", text_color="gray"); desc_label.grid(row=1, column=0, sticky="w", padx=5)
        current_row, clickable_widgets = 2, [master, top_frame, name_label, source_label, desc_label]
        if size := pkg.get('size'):
            size_label = ctk.CTkLabel(master, text=f"Size: {size}"); size_label.grid(row=current_row, column=0, sticky="w", padx=5); clickable_widgets.append(size_label); current_row += 1
        version_label = ctk.CTkLabel(master, text=f"Version: {pkg.get('version', 'N/A')}"); version_label.grid(row=current_row, column=0, sticky="w", padx=5, pady=(0,5)); clickable_widgets.append(version_label)
        # FIX: Pass the entire package dictionary to show_package_info
        for widget in clickable_widgets: widget.bind("<Button-1>", lambda e, p=pkg: self.show_package_info(p))
        self._add_hover_effect(clickable_widgets)

    def _create_installed_list_item(self, master: ctk.CTkFrame, pkg: dict):
        master.grid_columnconfigure(0, weight=1)
        clickable_widgets = [master]
        if pkg.get('source') == Config.SOURCE_FLATPAK:
            friendly_name_label = ctk.CTkLabel(master, text=pkg.get('friendly_name', 'N/A'), font=ctk.CTkFont(weight="bold")); friendly_name_label.grid(row=0, column=0, sticky="w", padx=5, pady=(5,0))
            name_label = ctk.CTkLabel(master, text=pkg.get('name', 'N/A'), text_color="gray"); name_label.grid(row=1, column=0, sticky="w", padx=5)
            size_label = ctk.CTkLabel(master, text=f"Size: {pkg.get('size', 'N/A')}"); size_label.grid(row=2, column=0, sticky="w", padx=5)
            version_label = ctk.CTkLabel(master, text=f"Version: {pkg.get('version', 'N/A')}"); version_label.grid(row=3, column=0, sticky="w", padx=5, pady=(0,5))
            clickable_widgets.extend([friendly_name_label, name_label, size_label, version_label]); row_span = 4
        else:
            name_label = ctk.CTkLabel(master, text=pkg.get('name', 'N/A'), font=ctk.CTkFont(weight="bold")); name_label.grid(row=0, column=0, sticky="w", padx=5, pady=(5,0))
            version_label = ctk.CTkLabel(master, text=f"Version: {pkg.get('version', 'N/A')}"); version_label.grid(row=1, column=0, sticky="w", padx=5, pady=(0,5))
            clickable_widgets.extend([name_label, version_label]); row_span = 2
        is_upgradable = pkg.get('name') in self.upgradable_packages
        status_text, status_color = ("Update available", "tomato") if is_upgradable else ("Up to date", "lightgreen")
        status_label = ctk.CTkLabel(master, text=status_text, text_color=status_color); status_label.grid(row=0, column=1, rowspan=row_span, sticky="e", padx=10); clickable_widgets.append(status_label)
        # FIX: Pass the entire package dictionary to show_package_info
        for widget in clickable_widgets: widget.bind("<Button-1>", lambda e, p=pkg: self.show_package_info(p))
        self._add_hover_effect(clickable_widgets)

    def change_page(self, view_type: str, delta: int):
        if view_type == 'search':
            self.search_page += delta
            frame = self.main_content.search_results_frame
        else:
            self.installed_page += delta
            frame = self.main_content.installed_frame
        self.update_page_view(view_type)
        self._scroll_to_top_animated(frame)

    def _scroll_to_top_animated(self, frame: ctk.CTkScrollableFrame):
        """Animates scrolling of a CTkScrollableFrame to the top."""
        def animation_step():
            current_pos = frame._parent_canvas.yview()[0]
            if current_pos < 0.001:
                frame._parent_canvas.yview_moveto(0)
                return
            new_pos = current_pos * 0.85
            frame._parent_canvas.yview_moveto(new_pos)
            self.after(15, animation_step)
        animation_step()

    def populate_groups(self):
        for widget in self.main_content.groups_frame.winfo_children(): widget.destroy()
        self.command_runner.run(["pacman", "-Sg"], self.parse_groups, cache_key="pacman_groups.cache")
    def parse_groups(self, output: str, source: Optional[str]):
        groups = sorted(list(set(line.split()[0] for line in output.strip().split('\n') if line)))
        for group_name in groups:
            btn = ctk.CTkButton(self.main_content.groups_frame, text=group_name, command=lambda g=group_name: self.search_group(g))
            btn.pack(fill="x", padx=10, pady=2)
    def search_group(self, group_name: str):
        self.main_content.tab_view.set("Search Results"); self.main_content.search_entry.delete(0, "end")
        self.command_runner.run(["pacman", "-Sgq", group_name], self.parse_group_packages, cache_key=f"group_{group_name}.cache")
    def parse_group_packages(self, output: str, source: Optional[str]):
        packages = [{"name": pkg_name, "desc": "Member of selected group", "source": Config.SOURCE_PACMAN} for pkg_name in sorted(output.strip().split('\n')) if pkg_name]
        self.search_results_data = packages; self.search_page = 1; self.update_page_view('search')

    def show_package_info(self, pkg: dict): InfoDialog(self, pkg)
    def show_queue_window(self): QueueDialog(self)
    def is_in_queue(self, pkg_name: str) -> Optional[str]:
        for item in self.package_queue:
            if item['pkg_name'] == pkg_name: return item['action']
        return None
    def add_to_queue(self, action: str, pkg_name: str, source: str):
        if self.is_in_queue(pkg_name): self.update_status(f"'{pkg_name}' is already in the queue."); return
        self.package_queue.append({"action": action, "pkg_name": pkg_name, "source": source})
        self.update_status(f"Added '{pkg_name}' to {action} queue.")
        self.sidebar.queue_button.configure(text=f"Show Queue ({len(self.package_queue)})")
    def remove_from_queue(self, pkg_name: str):
        self.package_queue = [p for p in self.package_queue if p['pkg_name'] != pkg_name]
        self.update_status(f"Removed '{pkg_name}' from queue.")
        self.sidebar.queue_button.configure(text=f"Show Queue ({len(self.package_queue)})")
    def clear_queue(self):
        self.package_queue.clear()
        self.sidebar.queue_button.configure(text="Show Queue (0)")
        self.update_status("Queue cleared.")
    def process_queue(self):
        if not self.package_queue: return

        dialog = ProcessDialog(self, "Processing Queue")
        queue_copy = self.package_queue.copy()
        self.clear_queue()

        jobs = []
        installs = [p['pkg_name'] for p in queue_copy if p['action'] == 'install' and p['source'] != Config.SOURCE_FLATPAK]
        removes = [p['pkg_name'] for p in queue_copy if p['action'] == 'remove' and p['source'] != Config.SOURCE_FLATPAK]
        flatpak_installs = [p['pkg_name'] for p in queue_copy if p['action'] == 'install' and p['source'] == Config.SOURCE_FLATPAK]
        flatpak_removes = [p['pkg_name'] for p in queue_copy if p['action'] == 'remove' and p['source'] == Config.SOURCE_FLATPAK]

        if installs: jobs.append({'cmd': ["yay", "-S", "--noconfirm"] + installs, 'sudo': True})
        if removes: jobs.append({'cmd': ["pacman", "-Rns", "--noconfirm"] + removes, 'sudo': True})
        if flatpak_installs: jobs.append({'cmd': ["flatpak", "install", "flathub", "-y", "--verbose"] + flatpak_installs, 'sudo': False})
        if flatpak_removes: jobs.append({'cmd': ["flatpak", "uninstall", "-y", "--verbose"] + flatpak_removes, 'sudo': False})

        def log_callback(line):
            dialog.append_log(line)

        def run_next_job(*args):
            if not jobs:
                dialog.append_log("\n\nAll operations complete.\n")
                dialog.on_complete()
                self.log_to_console("Package queue processing finished.")
                self.refresh_installed_list(force=True)
                return

            job = jobs.pop(0)
            self.command_runner.run(
                job['cmd'],
                callback=run_next_job,
                log_callback=log_callback,
                requires_sudo=job['sudo'],
                force_refresh=True,
                set_global_busy=False
            )

        run_next_job()


    def _parse_upgradable_system(self, output: str, source: Optional[str]):
        self.upgradable_packages.clear()
        for line in output.strip().split('\n'):
            if line: self.upgradable_packages.add(line.split()[0])
        self.update_page_view('installed')

    def _parse_upgradable_flatpak(self, output: str, source: Optional[str]):
        self.upgradable_packages.clear()
        for line in output.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 2: self.upgradable_packages.add(parts[1])
        self.update_page_view('installed')

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes == 0: return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

if __name__ == "__main__":
    app = App()
    app.mainloop()
















