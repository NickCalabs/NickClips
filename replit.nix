{pkgs}: {
  deps = [
    pkgs.yt-dlp
    pkgs.ffmpeg
    pkgs.ffmpeg-full
    pkgs.postgresql
    pkgs.openssl
  ];
}
