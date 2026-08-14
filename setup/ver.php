<?php
/**
 * Version tài nguyên CSS/JS = max filemtime.
 * Luôn no-store để trình duyệt lấy số version mới khi file đổi.
 */
header("Content-Type: application/javascript; charset=utf-8");
header("Cache-Control: no-store, no-cache, must-revalidate");
header("Pragma: no-cache");

$base = __DIR__;
$files = [
  "style.css",
  "common.js",
  "app.js",
];

$v = 0;
foreach ($files as $rel) {
  $path = $base . DIRECTORY_SEPARATOR . str_replace("/", DIRECTORY_SEPARATOR, $rel);
  if (is_file($path)) {
    $v = max($v, (int) filemtime($path));
  }
}

echo "window.SETUP_ASSET_VER=" . $v . ";\n";
