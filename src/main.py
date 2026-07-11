#!/usr/bin/env python3
# Simple task management application backend
import os

class Task:
    def __init__(self, title=''):
        self.title = title
        self.completed = False

def create_task(title):
    new_task = Task(title)
    return {'status': 'success', 'task': vars(new_task)}
