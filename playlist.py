import random

class PlaylistManager:
    def __init__(self):
        self.items = []
        self.current_index = -1
        self.shuffle = False
        self.repeat = 'none' # 'none', 'one', 'all'

    def add_item(self, path):
        if path not in self.items:
            self.items.append(path)

    def add_items(self, paths):
        for path in paths:
            self.add_item(path)

    def remove_item(self, index):
        if 0 <= index < len(self.items):
            self.items.pop(index)
            if self.current_index >= len(self.items):
                self.current_index = len(self.items) - 1

    def clear(self):
        self.items = []
        self.current_index = -1

    def get_next(self):
        if not self.items:
            return None
        
        if self.repeat == 'one':
            return self.items[self.current_index] if self.current_index != -1 else self.items[0]

        if self.shuffle:
            self.current_index = random.randint(0, len(self.items) - 1)
        else:
            self.current_index += 1
            if self.current_index >= len(self.items):
                if self.repeat == 'all':
                    self.current_index = 0
                else:
                    self.current_index = len(self.items) - 1
                    return None
        
        return self.items[self.current_index]

    def get_previous(self):
        if not self.items:
            return None
        
        self.current_index -= 1
        if self.current_index < 0:
            if self.repeat == 'all':
                self.current_index = len(self.items) - 1
            else:
                self.current_index = 0
        
        return self.items[self.current_index]

    def set_current(self, index):
        if 0 <= index < len(self.items):
            self.current_index = index
            return self.items[index]
        return None

    def get_current(self):
        if 0 <= self.current_index < len(self.items):
            return self.items[self.current_index]
        return None
