import tkinter as tk
from tkinter import simpledialog, messagebox, ttk
import pyperclip
import os
import json
import re
import sys
import subprocess
from spellchecker import SpellChecker

# --- Global variables to manage the state ---
is_monitoring = False
last_clipboard_content = ""
clipboard_buffer = []  # This list will collect notes during a session.

# --- File Path Management ---
SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
current_notes_filepath = os.path.join(SCRIPT_DIRECTORY, "clipboard_notes.txt")
CONFIG_FILE = os.path.join(SCRIPT_DIRECTORY, "config.json")

# --- OFFLINE PROOFREADING ENGINE ---
spell = SpellChecker()
dictionary = {}
simple_words = set()

def load_offline_data():
    """Loads the dictionary and simple words list from files into memory."""
    global dictionary, simple_words
    try:
        dict_path = os.path.join(SCRIPT_DIRECTORY, 'dictionary.json')
        words_path = os.path.join(SCRIPT_DIRECTORY, 'simple_words.txt')
        
        with open(dict_path, 'r', encoding='utf-8') as f:
            dictionary = json.load(f)
        with open(words_path, 'r', encoding='utf-8') as f:
            simple_words = set(word.strip().lower() for word in f)
        print("Offline dictionary and simple words loaded successfully.")
    except FileNotFoundError:
        messagebox.showerror("Error", "Could not find 'dictionary.json' or 'simple_words.txt'. Make sure they are in the same folder as the script.")
        return False
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load data files: {e}")
        return False
    return True

def proofread_text_offline(text_to_proofread):
    """The core offline engine. Corrects spelling and defines complex words."""
    final_proofread_text = []
    
    lines = text_to_proofread.split('\n')
    
    for line in lines:
        words = line.split(' ')
        new_words = []
        
        for word in words:
            is_bullet = word.startswith('•')
            clean_word = re.sub(r'^\W+|\W+$', '', word)
            
            if not clean_word:
                new_words.append(word)
                continue

            corrected_word_str = spell.correction(clean_word.lower())
            if corrected_word_str != clean_word.lower():
                if clean_word.istitle():
                    corrected_word_str = corrected_word_str.capitalize()
                elif clean_word.isupper():
                    corrected_word_str = corrected_word_str.upper()
                
                prefix = word[:word.find(clean_word)]
                suffix = word[word.find(clean_word) + len(clean_word):]
                word_to_process = prefix + corrected_word_str + suffix
            else:
                word_to_process = word
            
            final_word = word_to_process
            clean_word_for_dict = re.sub(r'^\W+|\W+$', '', word_to_process).lower()
            
            if clean_word_for_dict not in simple_words and clean_word_for_dict in dictionary:
                definition = dictionary[clean_word_for_dict]
                final_word = f"{word_to_process} ({definition})"
            
            new_words.append(final_word)

        final_proofread_text.append(' '.join(new_words))
        
    return "\n".join(final_proofread_text)

def save_note_to_file(text_to_save):
    """Appends the note to the currently active notes file."""
    with open(current_notes_filepath, "a", encoding="utf-8") as f:
        f.write(f"{text_to_save}\n\n")
    update_status_bar()

def process_and_save(batch_text):
    """Processes the entire batch of text and saves it."""
    if use_proofreader_var.get():
        status_label.config(text="⚙️ Proofreading offline...")
        proofread_text = proofread_text_offline(batch_text)
        save_note_to_file(proofread_text)
    else:
        save_note_to_file(batch_text)

def process_session_notes():
    """Processes everything in the buffer, adding bullet points."""
    global clipboard_buffer
    if not clipboard_buffer:
        return
    full_batch_text = "\n".join([f"• {note}" for note in clipboard_buffer])
    clipboard_buffer = []
    process_and_save(full_batch_text)

def check_clipboard():
    """Checks the clipboard and collects notes."""
    global last_clipboard_content
    if not is_monitoring:
        return
    try:
        current_content = pyperclip.paste()
        if current_content and current_content != last_clipboard_content:
            last_clipboard_content = current_content
            clipboard_buffer.append(current_content)
            status_label.config(text=f"📋 Note #{len(clipboard_buffer)} captured.")
    except pyperclip.PyperclipException:
        status_label.config(text="❌ Error accessing clipboard.")
    root.after(1000, check_clipboard)

def ask_for_new_file():
    """Processes old notes, then asks for a new filename."""
    global current_notes_filepath
    process_session_notes()
    new_name = simpledialog.askstring("New File", "Enter a name for the new notes file (no .txt needed):")
    if new_name and new_name.strip():
        filename = f"{new_name.strip()}.txt"
        current_notes_filepath = os.path.join(SCRIPT_DIRECTORY, filename)
        update_status_bar()
        
def update_status_bar():
    current_file = os.path.basename(current_notes_filepath)
    if is_monitoring:
        status_label.config(text=f"👀 Notes taking mode is ON (Saving to {current_file})")
    else:
        status_label.config(text=f"😴 Notes taking mode is OFF (Current file: {current_file})")

def toggle_monitoring():
    """Toggles monitoring and processes notes when turned OFF."""
    global is_monitoring, last_clipboard_content, clipboard_buffer
    if is_monitoring:
        process_session_notes()
    is_monitoring = not is_monitoring
    if is_monitoring:
        last_clipboard_content = pyperclip.paste()
        clipboard_buffer.clear()
        toggle_button.config(text="Monitoring: ON", style="On.TButton")
        check_clipboard()
    else:
        toggle_button.config(text="Monitoring: OFF", style="Off.TButton")
    update_status_bar()

# --- NEW: Settings and Convenience Functions ---
def save_settings():
    """Saves the current state of the checkboxes to a config file."""
    settings = {
        'use_proofreader': use_proofreader_var.get(),
        'always_on_top': always_on_top_var.get()
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(settings, f)

def load_settings():
    """Loads settings from the config file on startup."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            settings = json.load(f)
            use_proofreader_var.set(settings.get('use_proofreader', True))
            always_on_top_var.set(settings.get('always_on_top', False))
    except (FileNotFoundError, json.JSONDecodeError):
        # If file doesn't exist or is empty/corrupt, use defaults
        pass
    # Apply the loaded "always on top" setting
    toggle_always_on_top()

def on_closing():
    """Called when the user closes the window."""
    save_settings()
    root.destroy()

def toggle_always_on_top():
    """Toggles the 'always on top' attribute of the window."""
    root.attributes('-topmost', always_on_top_var.get())
    # No need to save here, will be saved on close

def open_notes_folder():
    """Opens the folder where notes are being saved."""
    if sys.platform == "win32":
        os.startfile(SCRIPT_DIRECTORY)
    elif sys.platform == "darwin": # macOS
        subprocess.call(["open", SCRIPT_DIRECTORY])
    else: # linux
        subprocess.call(["xdg-open", SCRIPT_DIRECTORY])

# --- Tkinter GUI seteup ---
root = tk.Tk()
root.title("Thing1's AI")
root.geometry("450x320") # Increased height for new options
root.configure(bg='#f0f0f0')

if not load_offline_data():
    root.destroy()
else:
    style = ttk.Style()
    style.configure("On.TButton", foreground="black", background="#FFFFFF", font=("Arial", 12, "bold"), padding=10)
    style.configure("Off.TButton", foreground="black", background="#e7e4e3", font=("Arial", 12, "bold"), padding=10)
    style.configure("TButton", font=("Arial", 12), padding=8)

    style.map("On.TButton", foreground=[('active', 'black'), ('!disabled', 'black')], background=[('active', '#DDDDDD'), ('!disabled', '#FFFFFF')])
    style.map("Off.TButton", foreground=[('active', 'black'), ('!disabled', 'black')], background=[('active', '#CCCCCC'), ('!disabled', "#e7e4e3")])

    button_frame = tk.Frame(root, bg='#f0f0f0')
    button_frame.pack(pady=10)

    toggle_button = ttk.Button(button_frame, text="Monitoring: OFF", command=toggle_monitoring, style="Off.TButton")
    toggle_button.pack(side=tk.LEFT, padx=10)

    new_file_button = ttk.Button(button_frame, text="Create New File", command=ask_for_new_file)
    new_file_button.pack(side=tk.LEFT, padx=10)

    proofreader_frame = tk.LabelFrame(root, text="Thing1's AI", bg='#f0f0f0', padx=10, pady=10)
    proofreader_frame.pack(padx=20, pady=5, fill="x")

    use_proofreader_var = tk.BooleanVar()
    proofreader_checkbox = tk.Checkbutton(proofreader_frame, text="Proofread notes with Thing1", variable=use_proofreader_var, bg='#f0f0f0')
    proofreader_checkbox.pack(anchor='w')

    # --- NEW: Tools & Settings Section ---
    tools_frame = tk.LabelFrame(root, text="Tools & Settings", bg='#f0f0f0', padx=10, pady=10)
    tools_frame.pack(padx=20, pady=5, fill="x")

    always_on_top_var = tk.BooleanVar()
    always_on_top_checkbox = tk.Checkbutton(tools_frame, text="Always on Top", variable=always_on_top_var, bg='#f0f0f0', command=toggle_always_on_top)
    always_on_top_checkbox.pack(side=tk.LEFT, anchor='w')

    open_folder_button = ttk.Button(tools_frame, text="Open Notes Folder", command=open_notes_folder)
    open_folder_button.pack(side=tk.RIGHT)

    status_label = tk.Label(root, text="", font=("Arial", 10), bg='#f0f0f0')
    status_label.pack(pady=10)

    # Load settings and set the closing protocol
    load_settings()
    root.protocol("WM_DELETE_WINDOW", on_closing)
    update_status_bar()
    root.mainloop()

