
if exists('g:pino_neovim_loaded')
    finish
endif
let g:pino_neovim_loaded = 1

nnoremap <leader>gd :execute 'PinoGoto '.expand('<cword>')<cr>
nnoremap <leader>gg :execute 'PinoGrep '.expand('<cword>')<cr>
nnoremap <leader>gc :execute 'PinoCode '.expand('<cword>')<cr>

