# Pino.neovim for the pino language server and neovm

import socket 
import json
import time
import os
import traceback

import neovim

def log_info(fmt, *args):
    if args:
        fmt = time.asctime() + fmt % args
    with open(r"E:\neovim.log", "a+") as f:
        f.write(fmt + "\n")

@neovim.plugin
class Pino(object):

    def __init__(self, vim):
        self.vim = vim
        self.pino_socket = None

    def _(self, args, cb):
        try:
            log_info("_ %s", locals())

            try:
                pino_socket = self._socket_setup()
                result = self._pino_send_request(pino_socket, *args)
            except socket.error:
                self.pino_socket = None
                pino_socket = self._socket_setup()
                result = self._pino_send_request(pino_socket, *args)
            log_info("_ result %s", result)

            cb and cb(result)
        except Exception, e:
            log_info("error %s", traceback.format_exc())

    def _quickfix(self, args):
        def cb(result):
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

        self._(args, cb)

    @neovim.command('PinoInit', range='', nargs='0', sync=False)
    def init(self, args, range):
        args = "init", 
        self._(args, None)

    @neovim.command('PinoReinit', range='', nargs='0', sync=False)
    def reinit(self, args, range):
        args = "reinit", 
        self._(args, None)

    @neovim.command('PinoStat', range='', nargs='0', sync=False)
    def stat(self, args, range):
        args = "stat", 
        self._(args, None)

    @neovim.command('PinoSave', range='', nargs='0', sync=False)
    def save(self, args, range):
        args = "save", 
        self._(args, None)

    @neovim.command('PinoGoto', range='', nargs='1', sync=False)
    def goto(self, args, range):
        args = "search_word", args[0], 0
        self._quickfix(args)

    @neovim.command('PinoGrep', range='', nargs='1', sync=False)
    def grep(self, args, range):
        args = "search_word", args[0], 2
        self._quickfix(args)

    @neovim.command('PinoCode', range='', nargs='1', sync=False)
    def code(self, args, range):
        args = "search_word", args[0], 1
        self._quickfix(args)

    @neovim.command('PinoFile', range='', nargs='1', sync=False)
    def file(self, args, range):
        args = "search_file", args[0]
        self._quickfix(args)

    @neovim.command('PinoCompletion', range='', nargs='1', sync=False)
    def completion(self, args, range):
        try:
            log_info("pino#completor %s", repr(locals()))
            if " " not in args[0]:
                return 
            name, ctx = args[0].split(" ", 1)
            name = json.loads(name)
            ctx = json.loads(ctx)
            args = "completion", ctx["typed"], 10
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
                    0,
                    ))
        except Exception, e:
            log_info("error %s", traceback.format_exc())

    def _socket_setup(self):
        pino_socket = self.pino_socket
        try:
            if pino_socket:
                pino_socket.getpeername()
                return pino_socket
            else:
                raise socket.error
        except socket.error:
            ip = self.vim.eval("g:pino_server_ip")
            port = int(self.vim.eval("g:pino_server_port"))
            pino_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            pino_socket.connect((ip, port))
            self.pino_socket = pino_socket
            return pino_socket

    def _pino_send_request(self, pino_socket, *args):
        action = args[0]
        args = args[1:]
        params = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": action,
            "params": {
                "cwf": self.vim.eval('expand("%:p")'),
                "cwd": self.vim.eval('getcwd()'),
                "args": args,
                "pid": os.getpid(),
                "xxx": id(self),
            }
        }

        binary = json.dumps(params).encode("utf8")
        length = len(binary)
        binary = b"Content-Length: %d\r\nContent-Type: application/vscode-jsonrpc; charset=utf8\r\n\r\n%s" % ( length, binary)

        pino_socket.sendall(binary)

        pino_recv_buffer = ""
        while True:
            data = pino_socket.recv(0xffff)
            if not data:
                # raise socket err
                pino_socket.recv(0xffff)
            pino_recv_buffer += data

            binary = pino_recv_buffer
            begin = 0
            end = len(binary)
            header_ending = b"\r\n\r\n"
            header_ending_l = len(header_ending)

            index = binary[begin:].find(header_ending)
            if index == -1:
                break
            headers = {}
            headers_list = binary[begin:begin + index].split(b"\r\n")
            for header in headers_list:
                i = header.find(b":")
                if i == -1:
                    continue
                key = header[:i]
                value = header[i+2:]
                headers[key] = value

            for k, v in headers.items():
                if v.isdigit():
                    headers[k] = int(v)

            cl = headers.get(b"Content-Length", 0)
            if begin + index + cl + header_ending_l <= end:
                b = begin + index + header_ending_l
                e = b + cl
                message = json.loads(binary[b:e])
                return message.get("result", "")

