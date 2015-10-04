# -*- coding: utf-8 -*-
u"""

.. moduleauthor:: Mark Hall <mark.hall@mail.room3b.eu>
"""
from subprocess import Popen, PIPE, TimeoutExpired

def extract_code(source):
    pre = []
    code = []
    post = []
    state = 0
    for line in source:
        if state == 0 and line.strip() == '// StartStudentCode':
            state = 1
        elif state == 1 and line.strip() == '// EndStudentCode':
            state = 2
        elif state == 0:
            pre.append(line)
        elif state == 1:
            code.append(line)
        elif state == 2:
            post.append(line)
    return ('\n'.join(pre), '\n'.join(code), '\n'.join(post))

def run_test(command, parameters, submission_file):
    with Popen([command] + parameters, stdout=PIPE, stderr=PIPE) as process:
        try:
            stdout, stderr = process.communicate(timeout=60)
            stdout = stdout.decode('utf-8')
            stderr = stderr.decode('utf-8')
        except TimeoutExpired:
            stdout = None
            stderr = 'Test failed due to timeout'
        if process.returncode == 0:
            submission_file.score = 2
            if stdout:
                submission_file.feedback.append(stdout)
        else:
            submission_file.score = 1
            if stdout:
                submission_file.feedback.append(stdout)
            if stderr:
                submission_file.feedback.append(stderr)
    