<?php
/**
 * Reverse proxy: trang tick/ → api.py 127.0.0.1:5001.
 * Timeout dài hơn mt5 vì query file tick hàng triệu dòng.
 * Hỗ trợ JSON và upload multipart.
 */

$API_HOST = "127.0.0.1";
$API_PORT = 5001;

$path = isset($_GET["path"]) ? $_GET["path"] : "/api/tick/files";
if ($path === "" || $path[0] !== "/") {
    $path = "/" . $path;
}

$target_url = "http://{$API_HOST}:{$API_PORT}{$path}";
$method = $_SERVER["REQUEST_METHOD"];
$is_multipart = !empty($_FILES);

function forward_json($url, $method, $body, &$http_code, &$error) {
    if (function_exists("curl_init")) {
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 2);
        curl_setopt($ch, CURLOPT_TIMEOUT, 180);
        curl_setopt($ch, CURLOPT_HTTPHEADER, ["Content-Type: application/json", "Connection: keep-alive"]);
        curl_setopt($ch, CURLOPT_TCP_NODELAY, true);
        if ($body !== "") {
            curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
        }
        $response = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE) ?: 502;
        $error = $response === false ? curl_error($ch) : "";
        curl_close($ch);
        return $response;
    }

    $context = stream_context_create([
        "http" => [
            "method" => $method,
            "header" => "Content-Type: application/json\r\n",
            "content" => $body,
            "timeout" => 180,
            "ignore_errors" => true,
        ],
    ]);
    $response = @file_get_contents($url, false, $context);
    $http_code = 200;
    if (isset($http_response_header)) {
        foreach ($http_response_header as $header_line) {
            if (preg_match('/^HTTP\/\S+\s+(\d+)/', $header_line, $m)) {
                $http_code = (int) $m[1];
                break;
            }
        }
    }
    $error = $response === false ? "Không kết nối được (file_get_contents)" : "";
    return $response;
}

function forward_multipart($url, &$http_code, &$error) {
    if (!function_exists("curl_init")) {
        $http_code = 500;
        $error = "Cần ext-curl để upload file.";
        return false;
    }
    $post = [];
    foreach ($_POST as $key => $value) {
        $post[$key] = $value;
    }
    foreach ($_FILES as $key => $file) {
        if (!isset($file["tmp_name"]) || $file["error"] !== UPLOAD_ERR_OK) {
            $http_code = 400;
            $error = "Upload lỗi (mã " . (isset($file["error"]) ? $file["error"] : "?") . ").";
            return false;
        }
        $post[$key] = new CURLFile($file["tmp_name"], $file["type"] ?: "text/csv", $file["name"]);
    }
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $post);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 2);
    curl_setopt($ch, CURLOPT_TIMEOUT, 180);
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE) ?: 502;
    $error = $response === false ? curl_error($ch) : "";
    curl_close($ch);
    return $response;
}

if ($is_multipart) {
    $response = forward_multipart($target_url, $http_code, $error);
} else {
    $body = file_get_contents("php://input");
    $response = forward_json($target_url, $method, $body, $http_code, $error);
}

header("Content-Type: application/json; charset=utf-8");

if ($response === false) {
    http_response_code(502);
    echo json_encode([
        "error" => "Không gọi được api.py tại {$target_url}. "
            . "Chạy start_server.bat trên cùng máy WAMP. Chi tiết: {$error}",
    ]);
    exit;
}

http_response_code($http_code);
echo $response;
