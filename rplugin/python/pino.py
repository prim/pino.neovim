# Pino.neovim for the pino language server and neovm

import os
import json
import time
import socket 
import traceback
import requests

import neovim

_log_file_path = os.path.join(os.path.dirname(__file__), "pino.neovim.log")

def log_info(fmt, *args):
    if args:
        fmt = time.asctime() + fmt % args
    with open(_log_file_path, "a+") as f:
        f.write(fmt + "\n")

@neovim.plugin
class Pino(object):

    def __init__(self, vim):
        self.vim = vim
        self.session = requests.Session()

        ip = vim.eval("g:pino_server_ip")
        port = vim.eval("g:pino_server_port")
        self.url = "http://%s:%s/pino" % (ip, port)

    def _(self, *args):
        try:
            log_info("_ %s", locals())
            args = list(args)
            method_name = args.pop(0)
            method_params = {
                "cwf": self.vim.eval('expand("%:p")'),
                "cwd": self.vim.eval('getcwd()'),
                "args": args,
                "pid": os.getpid(),
                # "xxx": id(self),
            }
            result = self.session.post(self.url, json={"method-name": method_name, "method-params": method_params})
            log_info(result.content)
            data = json.loads(result.content)
            result = data.get("result", "")
            return result
        except Exception, e:
            log_info("error %s", traceback.format_exc())

    def _quickfix(self, *args):
        result = self._(*args)

        log_info("_quickfix %s %s", args, result)
        word = args[1]
        type_ = args[2]
        if type_ == 0 and len(result) == 1:
            filename = result[0]["filename"]
            bufnr = self.vim.funcs.bufnr(filename)
            if bufnr != -1:
                cmd = "buffer %d" % bufnr
            else:
                cmd = "edit! %s" % filename
            self.vim.command(cmd)
            lnum = result[0]["lnum"] + 1
            col = result[0]["text"].find(word)
            self.vim.funcs.cursor(lnum, col)
            return 
        self.vim.funcs.setqflist(result)
        self.vim.command("copen")

    @neovim.command('PinoInit', range='', nargs='0', sync=False)
    def init(self, args, range):
        self._("Init")

    @neovim.command('PinoReinit', range='', nargs='0', sync=False)
    def reinit(self, args, range):
        self._("Reinit")

    @neovim.command('PinoStat', range='', nargs='0', sync=False)
    def stat(self, args, range):
        self._("Stat")

    @neovim.command('PinoSave', range='', nargs='0', sync=False)
    def save(self, args, range):
        self._("Save")

    @neovim.command('PinoGoto', range='', nargs='1', sync=False)
    def goto(self, args, range):
        self._quickfix("SearchWord", args[0], 0)

    @neovim.command('PinoGrep', range='', nargs='1', sync=False)
    def grep(self, args, range):
        self._quickfix("SearchWord", args[0], 2)

    @neovim.command('PinoCode', range='', nargs='1', sync=False)
    def code(self, args, range):
        self._quickfix("SearchWord", args[0], 1)

    @neovim.command('PinoFile', range='', nargs='1', sync=False)
    def file(self, args, range):
        self._quickfix("SearchFile", args[0], 3)

    @neovim.command('PinoCompletion', range='', nargs='1', sync=False)
    def completion(self, args, range):
        # TODO 
        try:
            log_info("pino#completor %s", repr(locals()))
            if " " not in args[0]:
                return 
            name, ctx = args[0].split(" ", 1)
            name = json.loads(name)
            ctx = json.loads(ctx)
            args = "Completion", ctx["typed"], 10
            pino_socket = self._socket_setup()
            result = self._pino_send_request(pino_socket, *args)
            log_info("result %s", repr(result))

            if result:
                items = result.split("\n")
                col = ctx["col"]
                typed = ctx["typed"]
                kw = self.vim.funcs.matchstr(typed, '\w\+$')
                kwlen = len(kw)
                startcol = col - kwlen
                self.vim.command("call asyncomplete#complete(%s, %s, %s, %s, %s)" % (
                    json.dumps(name),
                    json.dumps(ctx),
                    json.dumps(startcol),
                    json.dumps(items),
                    1, # force refresh
                    ))
        except Exception, e:
            log_info("error %s", traceback.format_exc())

