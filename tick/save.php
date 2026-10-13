<?php
/**
 * Ghi CSV vào cùng folder trang (www/tick).
 * File lớn: JS cắt ~1 MB/khối (index/total/size), ghép thành .part rồi đổi tên .csv.
 */
header_remove("X-Powered-By");
header("Content-Type: application/json; charset=utf-8");
header("X-Content-Type-Options: nosniff");

ini_set("display_errors", "0");
ini_set("max_execution_time", "0");

function fail($code, $msg) {
    http_response_code($code);
    echo json_encode(["error" => $msg], JSON_UNESCAPED_UNICODE);
    exit;
}

function ok($payload) {
    echo json_encode($payload, JSON_UNESCAPED_UNICODE);
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

$max_chunk = 8 * 1024 * 1024;
$max_paste = 8 * 1024 * 1024;
$dir = __DIR__;

if (!empty($_FILES["file"]) && is_array($_FILES["file"])) {
    $file = $_FILES["file"];
    $code = (int) ($file["error"] ?? UPLOAD_ERR_NO_FILE);
    if ($code !== UPLOAD_ERR_OK) {
        if ($code === UPLOAD_ERR_INI_SIZE || $code === UPLOAD_ERR_FORM_SIZE) {
            fail(400, "Khối vượt upload_max_filesize của PHP.");
        }
        fail(400, "Upload lỗi (mã " . $code . ").");
    }
    if (($file["size"] ?? 0) > $max_chunk) {
        fail(400, "Mỗi khối tối đa 8 MB.");
    }
    $name = safe_name($file["name"] ?? "upload.csv");
    if (!empty($_POST["filename"])) {
        $name = safe_name($_POST["filename"]);
    }
    $index = isset($_POST["index"]) ? (int) $_POST["index"] : 0;
    $total = isset($_POST["total"]) ? (int) $_POST["total"] : 1;
    $full = isset($_POST["size"]) ? (int) $_POST["size"] : 0;
    if ($index < 0 || $total < 1 || $index >= $total) {
        fail(400, "index/total không hợp lệ.");
    }

    $part = $dir . DIRECTORY_SEPARATOR . $name . ".part";
    $dest = $dir . DIRECTORY_SEPARATOR . $name;
    if ($index > 0 && !is_file($part)) {
        fail(400, "Thiếu file tạm .part — gửi lại từ khối đầu.");
    }
    $chunkData = file_get_contents($file["tmp_name"]);
    if ($chunkData === false) {
        fail(500, "Không đọc được khối tạm.");
    }
    if ($chunkData === "" && ($full > 0 || $total > 1)) {
        fail(400, "Khối upload trống (index " . $index . ").");
    }
    $flags = $index === 0 ? 0 : FILE_APPEND;
    if (file_put_contents($part, $chunkData, $flags) === false) {
        fail(500, "Không ghi được file vào " . $dir);
    }

    if ($index < $total - 1) {
        ok([
            "ok" => true,
            "name" => $name,
            "index" => $index,
            "total" => $total,
            "partial" => true,
            "dir" => $dir,
        ]);
    }

    clearstatcache(true, $part);
    $got = filesize($part);
    if ($got === 0) {
        @unlink($part);
        fail(400, "File trống.");
    }
    if ($full > 0 && $got !== $full) {
        @unlink($part);
        fail(400, "Dung lượng sau khi ghép không khớp (" . $got . " vs " . $full . ").");
    }
    if (is_file($dest) && !@unlink($dest)) {
        fail(500, "Không ghi đè được " . $name);
    }
    if (!@rename($part, $dest)) {
        fail(500, "Không đổi tên file tạm thành " . $name);
    }
    ok(["ok" => true, "name" => $name, "size" => filesize($dest), "dir" => $dir]);
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
if (strlen($text) > $max_paste) {
    fail(400, "Nội dung dán tối đa 8 MB.");
}
$name = safe_name($data["filename"] ?? "pasted.csv");
$dest = $dir . DIRECTORY_SEPARATOR . $name;
if (file_put_contents($dest, $text) === false) {
    fail(500, "Không ghi được file vào " . $dir);
}
ok(["ok" => true, "name" => $name, "size" => strlen($text), "dir" => $dir]);
