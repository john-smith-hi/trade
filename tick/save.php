<?php
/**
 * Ghi CSV vào cùng folder trang (www/tick). Không đi qua api.py.
 */
header_remove("X-Powered-By");
header("Content-Type: application/json; charset=utf-8");
header("X-Content-Type-Options: nosniff");

ini_set("display_errors", "0");

function fail($code, $msg) {
    http_response_code($code);
    echo json_encode(["error" => $msg], JSON_UNESCAPED_UNICODE);
    exit;
}

function safe_name($name) {
    $base = basename((string) $name);
    $base = preg_replace('/[\x00-\x1f\x7f<>:"|?*\\\\\/]/', "_", $base);
    $base = trim($base);
    if ($base === "" || $base[0] === ".") {
        fail(400, "Tên file không hợp lệ.");
    }
    if (!preg_match('/\.csv$/i', $base)) {
        $base .= ".csv";
    }
    if (!preg_match('/^[A-Za-z0-9._()\[\] -]{1,180}$/', $base)) {
        fail(400, "Tên file không hợp lệ.");
    }
    return $base;
}

$max = 64 * 1024 * 1024;
$dir = __DIR__;

if (!empty($_FILES["file"]) && is_array($_FILES["file"])) {
    $file = $_FILES["file"];
    if (($file["error"] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK) {
        fail(400, "Upload lỗi (mã " . (int) ($file["error"] ?? 0) . ").");
    }
    if (($file["size"] ?? 0) > $max) {
        fail(400, "Upload tối đa 64 MB. File tháng copy thẳng vào folder này.");
    }
    $name = safe_name($file["name"] ?? "upload.csv");
    $dest = $dir . DIRECTORY_SEPARATOR . $name;
    if (!move_uploaded_file($file["tmp_name"], $dest)) {
        fail(500, "Không ghi được file vào " . $dir);
    }
    echo json_encode(["ok" => true, "name" => $name, "size" => filesize($dest), "dir" => $dir], JSON_UNESCAPED_UNICODE);
    exit;
}

$raw = file_get_contents("php://input");
$data = json_decode($raw, true);
if (!is_array($data)) {
    fail(400, "Body JSON không hợp lệ.");
}
$text = (string) ($data["csv"] ?? $data["text"] ?? "");
if (trim($text) === "") {
    fail(400, "Chưa có nội dung CSV.");
}
if (strlen($text) > $max) {
    fail(400, "Nội dung dán tối đa 64 MB.");
}
$name = safe_name($data["filename"] ?? "pasted.csv");
$dest = $dir . DIRECTORY_SEPARATOR . $name;
if (file_put_contents($dest, $text) === false) {
    fail(500, "Không ghi được file vào " . $dir);
}
echo json_encode(["ok" => true, "name" => $name, "size" => strlen($text), "dir" => $dir], JSON_UNESCAPED_UNICODE);
