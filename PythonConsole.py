# Copyright 2020 Cadwork.
# All rights reserved.
# This file is part of PythonConsole,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.


import os
import rlcompleter
import sys
import tkinter as tk
from abc import ABC
from threading import Lock
from tkinter import INSERT, END, SEL, SEL_FIRST, SEL_LAST, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from typing import TextIO


class Console(ScrolledText):
  def __init__(self, master=None, **kwargs):
    kwargs.setdefault('background', 'lavender')
    kwargs.setdefault('foreground', 'dark green')
    kwargs.setdefault('font', ('consolas', 9, 'bold'))
    self._prompt = '>>> '
    self.history = []
    self.complete = rlcompleter.Completer(globals()).complete
    self.write_lock = Lock()

    ScrolledText.__init__(self, master, **kwargs)
    self.tag_config('prompt', foreground='firebrick')
    self.tag_config('error', foreground='red')
    self.tag_config('cmd', foreground='sienna')
    self.bindings()
    sys.stdout = StdoutReDirector(self)
    sys.stderr = StderrReDirector(self)
    self.prompt()
    self.focus_set()

  def bindings(self):
    self.bind('<Return>', self.return_event)
    self.bind('<KeyRelease-Up>', self.up_event)
    self.bind('<BackSpace>', self.backspace_event)
    self.bind('<Delete>', self.delete_event)
    self.bind('<Tab>', self.tab_event)
    self.bind('<Enter>', self.focus)

  def run(self, command=None):
    self.tag_add('cmd', 'limit', "%s-1c" % INSERT)
    if command is None:
      command = self.get('limit', END).lstrip()
      self.history.append(command)
    self.evaluate(command)
    self.prompt()

  def evaluate(self, command):
    try:
      compile(command, '<stdin>', 'eval')
      try:
        eval_result = eval(command, globals())
        if eval_result is not None:
          self.write(END, eval_result, ('output',))
      except Exception as error:
        self.write(END, 'ERROR:\n%s\n' % error, ('error',))
    except SyntaxError:
      try:
        exec(command, globals())
      except Exception as error:
        self.write(END, 'ERROR:\n%s\n' % error, ('error',))

  def prompt(self):
    if len(get_last_line(self)):
      self.write(END, '\n')
    self.write(END, self._prompt, ('prompt',))
    self.mark_set(INSERT, END)
    self.mark_set('limit', '%s-1c' % INSERT)
    self.see(END)

  def write(self, index, chars, *args):
    self.write_lock.acquire()
    self.insert(index, chars, *args)
    self.write_lock.release()

  def backspace_event(self, _):
    if self.tag_nextrange(SEL, '1.0', END) and self.compare(SEL_FIRST, '>=', 'limit'):
      self.delete(SEL_FIRST, SEL_LAST)
    elif self.compare(INSERT, '!=', '1.0') and self.compare(INSERT, '>', 'limit+1c'):
      self.delete('%s-1c' % INSERT)
      self.see(INSERT)
    return 'break'

  def delete_event(self, _):
    if self.tag_nextrange(SEL, '1.0', END) and self.compare(SEL_FIRST, '>=', 'limit'):
      self.delete(SEL_FIRST, SEL_LAST)
    elif self.compare(INSERT, '>', 'limit+1c'):
      self.delete('%s-1c' % INSERT)
      self.see(INSERT)
    return 'break'

  def return_event(self, _):
    if self.compare(INSERT, '<', 'limit'):
      command = self.get_current_command()
      if command:
        self.insert_command(command)
        return 'break'
    else:
      self.mark_set(INSERT, END)
      self.write(END, '\n')
      self.run()
    return 'break'

  def up_event(self, _):
    position = self.tag_prevrange('cmd', INSERT, '1.0')
    if not position:
      return
    first_index, second_index = position
    line, command = index_to_tuple(self, first_index)
    index = str(line) + '.end'
    self.mark_set(INSERT, index)
    self.see(INSERT)
    return 'break'

  def tab_event(self, _):
    if self.compare(INSERT, '<', 'limit'):
      return 'break'
    command = self.get('limit', END).strip()
    completions = []
    iteration = 0
    done = dict()
    while True:
      complete = self.complete(command, iteration)
      if complete is None or complete in done:
        break
      done[complete] = None
      completions.append(complete)
      iteration += 1
    if completions:
      if len(completions) == 1:
        self.insert_command(completions[0])
      else:
        self._print(display_list(completions))
        if command:
          pass
          self.insert_command(command)
    return 'break'

  def insert_command(self, cmd):
    self.delete('limit+1c', END)
    self.write(END, cmd, ('cmd',))
    self.mark_set(INSERT, END)
    self.see(END)

  def get_current_command(self):
    ranges = self.tag_ranges('cmd')
    insertion = '%s-1c' % INSERT
    for i in range(0, len(ranges), 2):
      start = ranges[i]
      stop = ranges[i + 1]
      if self.compare(start, '<=', insertion) and self.compare(insertion, '<=', stop):
        return self.get(start, stop).lstrip()
    return ''

  def _print(self, text):
    self.tag_add('cmd', 'limit', "%s-1c" % END)
    self.write(END, '\n')
    self.write(END, text)
    self.prompt()

  def clear(self):
    self.delete(1.0, END)
    self.prompt()

  def focus(self, _):
    self.focus_set()

  def none(self, event=None):
    pass


class StdoutReDirector(TextIO, ABC):
  def __init__(self, text_widget):
    self.text = text_widget

  def write(self, string):
    sys.__stdout__.write(string)
    first_line, first_command = index_to_tuple(self.text, '%s-1c' % END)
    second_line, second_command = index_to_tuple(self.text, 'limit')
    if first_line == second_line:
      self.text.write('limit-3c', string)
    else:
      self.text.write('end', string)
    self.text.see('end')

  def writelines(self, lines):
    sys.__stdout__.writelines(lines)
    for line in lines:
      self.text.write(line)

  def flush(self):
    sys.__stdout__.flush()


def index_to_tuple(text, index):
  return tuple(map(int, text.index(index).split(".")))


def get_last_line(text):
  line, command = index_to_tuple(text, END)
  line -= 1
  start = str(line) + '.' + str(0)
  end = str(line) + '.end'
  return text.get(start, end)


def display_list(input_list):
  text = ""
  iteration = 1
  for element in sorted(input_list):
    element = str(element)
    text += ' ' + element + '\n'
    iteration += 1
  return text


class StderrReDirector(TextIO, ABC):
  def __init__(self, text_widget):
    self.text = text_widget

  def write(self, string):
    sys.__stderr__.write(string)
    first_line, first_command = index_to_tuple(self.text, '%s-1c' % END)
    second_line, second_command = index_to_tuple(self.text, 'limit')
    if first_line == second_line:
      self.text.write('limit-3c', string)
    else:
      self.text.write('end', string)
    self.text.see('end')

  def writelines(self, lines):
    sys.__stderr__.writelines(lines)
    for line in lines:
      self.text.write(line)

  def flush(self):
    sys.__stderr__.flush()


class Application(tk.Frame):
  def __init__(self, master=None):
    super().__init__(master)
    self.master = master

    self.menubar = tk.Menu(self)

    file_menu = tk.Menu(self.menubar, tearoff=0)
    self.menubar.add_cascade(label='File', menu=file_menu)
    file_menu.add_command(label='Save As', command=self.save_as_action)
    file_menu.add_command(label='Close', command=self.close_action)

    edit_menu = tk.Menu(self.menubar, tearoff=0)
    self.menubar.add_cascade(label='Edit', menu=edit_menu)
    edit_menu.add_command(label='Select All', command=self.select_all_action)
    edit_menu.add_separator()
    edit_menu.add_command(label='Copy', command=self.copy_action)
    edit_menu.add_separator()
    edit_menu.add_command(label='Clear', command=self.clear_action)

    help_menu = tk.Menu(self.menubar, tearoff=0)
    self.menubar.add_cascade(label='Help', menu=help_menu)
    help_menu.add_command(label='Help', command=self.help_action)
    help_menu.add_separator()
    help_menu.add_command(label='About', command=self.about_action)

    self.master.config(menu=self.menubar)
    self.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    self.console = Console(self, width=125, height=30)
    self.console.pack(fill='both', expand=True)
    self.console.focus_set()
    self.pack()

  def save_as_action(self):
    file = filedialog.asksaveasfile(mode='w', filetypes=[("Python Script", "*.py")])
    if file is None:
      return
    self.console.tag_add(SEL, '1.0', END)
    self.console.mark_set(INSERT, '1.0')
    self.console.see(INSERT)
    selection = self.console.get('sel.first', 'sel.last')
    self.console.tag_remove(SEL, '1.0', END)
    self.console.mark_unset(INSERT, '1.0')
    self.console.mark_set(INSERT, END)
    for line in selection.split('\n'):
      if '>>> ' in line:
        clean_line = line.replace('>>> ', '')
        file.write(clean_line + '\n')
    file.close()

  def close_action(self):
    self.master.destroy()

  def select_all_action(self):
    self.console.tag_add(SEL, '1.0', END)
    self.console.mark_set(INSERT, '1.0')
    self.console.see(INSERT)

  def copy_action(self):
    self.clipboard_clear()
    selection = self.console.get('sel.first', 'sel.last')
    self.clipboard_append(selection)

  def clear_action(self):
    self.console.delete(1.0, tk.END)
    self.console.prompt()

  def help_action(self):
    os.startfile('https://github.com/CadworkMontreal/PythonConsole')

  def about_action(self):
    messagebox.showinfo('About PythonConsole',
                        'Cadwork Python Console 1.1\nSee the LICENSE file.\nCopyright 2020 Cadwork')


if __name__ == '__main__':
  root = tk.Tk()
  root.title('Cadwork Python Console')
  application = Application(master=root)
  application.pack(fill='both', expand=True)
  x_position = (root.winfo_screenwidth() / 2) - 450
  y_position = (root.winfo_screenheight() / 2) - root.winfo_reqheight()
  root.geometry('+%d+%d' % (x_position, y_position))
  root.mainloop()
