<?php
/**
 * Reverse proxy: chuyển request sang api.py (127.0.0.1:5001).
 *
 * Hai cách gọi:
 * 1) UI:  proxy.php?path=/api/accounts
 *         proxy.php?path=/api/quote%3Faccount%3Dx%26symbol%3DY
 * 2) Ngrok/Apache rewrite tới /api/... → dùng REQUEST_URI (xem api/gateway.php)
 *
 * Lý do: api.py chỉ bind localhost; ngrok/máy khác không gọi thẳng :5001 được.
 */

$API_HOST = "127.0.0.1";
$API_PORT = 5001;

function build_target_url($host, $port) {
    // Ưu tiên path= từ UI (common.js).
    if (isset($_GET["path"]) && $_GET["path"] !== "") {
        $path = $_GET["path"];
        if ($path[0] !== "/") {
            $path = "/" . $path;
        }
        return "http://{$host}:{$port}{$path}";
    }

    // Fallback: forward nguyên REQUEST_URI nếu path bắt đầu bằng /api/
    $uri = $_SERVER["REQUEST_URI"] ?? "/api/accounts";
    $parts = parse_url($uri);
    $path = $parts["path"] ?? "/api/accounts";
    $query = $parts["query"] ?? "";
    if (strpos($path, "/api/") !== 0 && $path !== "/api") {
        $path = "/api/accounts";
        $query = "";
    }
    return "http://{$host}:{$port}{$path}" . ($query !== "" ? "?{$query}" : "");
}

$target_url = build_target_url($API_HOST, $API_PORT);
$method = $_SERVER["REQUEST_METHOD"] ?? "GET";
$body = file_get_contents("php://input");

function forward_request($url, $method, $body, &$http_code, &$error) {
    if (function_exists("curl_init")) {
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 2);
        curl_setopt($ch, CURLOPT_TIMEOUT, 60);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            "Content-Type: application/json",
            "Connection: keep-alive",
            "ngrok-skip-browser-warning: 1",
        ]);
        curl_setopt($ch, CURLOPT_TCP_NODELAY, true);
        if ($body !== false && $body !== "") {
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
            "timeout" => 60,
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

$response = forward_request($target_url, $method, $body, $http_code, $error);

header("Content-Type: application/json; charset=utf-8");
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Headers: Content-Type, ngrok-skip-browser-warning");
header("Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS");

if (($_SERVER["REQUEST_METHOD"] ?? "") === "OPTIONS") {
    http_response_code(204);
    exit;
}

if ($response === false) {
    http_response_code(502);
    echo json_encode([
        "error" => "Không gọi được tới api.py tại {$target_url}. Hãy chắc chắn đã chạy start_api.bat "
            . "trên máy chủ WampServer này. Chi tiết lỗi: {$error}",
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

http_response_code($http_code);
echo $response;
