{pkgs}: {
  deps = [
    pkgs.glibcLocales
    pkgs.python311Packages.ansible-kernel
    pkgs.ansible-builder
    pkgs.ansible-navigator
    pkgs.ansible-lint
    pkgs.ansible
    pkgs.aha
    pkgs.vimPlugins.vim-plug
    pkgs.vimPlugins.vim-plugin-AnsiEsc
    pkgs.openssh
    pkgs.vim
    pkgs.ugrep
    pkgs.github-cli
  ];
}
