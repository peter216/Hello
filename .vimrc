set autoindent        " Auto-indent new lines
set expandtab         " Use spaces instead of tabs
set shiftwidth=4      " Number of auto-indent spaces
set smartindent       " Enable smart-indent
set smarttab          " Enable smart-tabs
set softtabstop=4     " Number of spaces per Tab
set background=dark   " Color scheme for dark background
syntax on

call plug#begin()

Plug 'vim-scripts/AnsiEsc.vim'

call plug#end()
