<?php
header_remove("X-Powered-By");
header("Content-Type: text/html; charset=utf-8");
header("X-Content-Type-Options: nosniff");
header("X-Frame-Options: DENY");
header("Referrer-Policy: no-referrer");
header("Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self' https://api.frankfurter.dev; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'");
header("Cache-Control: no-cache");
readfile(__DIR__ . DIRECTORY_SEPARATOR . "index.html");
