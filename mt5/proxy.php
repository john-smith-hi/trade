<?php
/**
 * Reverse proxy đơn giản: chuyển tiếp request từ trang web (kể cả truy cập
 * qua ngrok / từ máy khác) sang api.py đang chạy cục bộ trên CHÍNH máy chủ
 * WampServer này (127.0.0.1:5001).
 *
 * Lý do cần file này:
 * - api.py chỉ bind 127.0.0.1 (an toàn, không expose trực tiếp ra internet)
 *   nên máy khác/ngrok không gọi thẳng tới http://localhost:5001 được.
 * - Trang web và proxy.php này cùng nằm trên 1 origin (dù truy cập qua
 *   ngrok https hay LAN), nên không bị chặn mixed-content / CORS.
 *
 * Cách dùng từ JS: fetch("proxy.php?path=" + encodeURIComponent("/api/accounts"))
 */

$API_HOST = "127.0.0.1";
$API_PORT = 5001;

$path = isset($_GET["path"]) ? $_GET["path"] : "/api/accounts";
if ($path === "" || $path[0] !== "/") {
    $path = "/" . $path;
}

$target_url = "http://{$API_HOST}:{$API_PORT}{$path}";
$method = $_SERVER["REQUEST_METHOD"];
$body = file_get_contents("php://input");

function forward_request($url, $method, $body, &$http_code, &$error) {
    if (function_exists("curl_init")) {
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 2);
        curl_setopt($ch, CURLOPT_TIMEOUT, 60);
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

    // Máy không có ext-curl -> dùng file_get_contents làm phương án dự phòng.
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

if ($response === false) {
    http_response_code(502);
    echo json_encode([
        "error" => "Không gọi được tới api.py tại {$target_url}. Hãy chắc chắn đã chạy start_api.bat "
            . "trên máy chủ WampServer này. Chi tiết lỗi: {$error}",
    ]);
    exit;
}

http_response_code($http_code);
echo $response;
