<?php
/**
 * Version CSS/JS = max filemtime. no-store để trình duyệt lấy số mới khi file đổi.
 */
header_remove("X-Powered-By");
header("Content-Type: application/javascript; charset=utf-8");
header("X-Content-Type-Options: nosniff");
header("Cache-Control: no-store, no-cache, must-revalidate");
header("Pragma: no-cache");

ini_set("display_errors", "0");

$base = __DIR__;
$files = ["style.css", "analyze.js", "app.js", "theme.js", "assets.js", "load.js"];

$v = 0;
foreach ($files as $rel) {
  $path = $base . DIRECTORY_SEPARATOR . $rel;
  if (is_file($path)) {
    $v = max($v, (int) filemtime($path));
  }
}

echo "window.HISTORY_ASSET_VER=" . $v . ";\n";
