<?php
$API_HOST = "127.0.0.1";
$API_PORT = 5001;
$sub = isset($_GET["__path"]) ? (string) $_GET["__path"] : "";
$sub = str_replace("\\", "/", $sub);
$sub = ltrim($sub, "/");
$path = "/api" . ($sub !== "" ? "/" . $sub : "");
$query = $_GET;
unset($query["__path"]);
$qs = http_build_query($query);
$target_url = "http://{$API_HOST}:{$API_PORT}{$path}" . ($qs !== "" ? "?{$qs}" : "");
$method = $_SERVER["REQUEST_METHOD"] ?? "GET";
$body = file_get_contents("php://input");
header("Content-Type: application/json; charset=utf-8");
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Headers: Content-Type, ngrok-skip-browser-warning");
header("Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS");
if ($method === "OPTIONS") { http_response_code(204); exit; }
if (!function_exists("curl_init")) {
  http_response_code(500);
  echo json_encode(["error" => "PHP thiếu ext-curl"], JSON_UNESCAPED_UNICODE);
  exit;
}
$ch = curl_init($target_url);
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 2);
curl_setopt($ch, CURLOPT_TIMEOUT, 60);
curl_setopt($ch, CURLOPT_HTTPHEADER, ["Content-Type: application/json", "Connection: keep-alive", "ngrok-skip-browser-warning: 1"]);
if ($body !== false && $body !== "") { curl_setopt($ch, CURLOPT_POSTFIELDS, $body); }
$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE) ?: 502;
$error = $response === false ? curl_error($ch) : "";
curl_close($ch);
if ($response === false) {
  http_response_code(502);
  echo json_encode(["error" => "Không gọi được api.py tại {$target_url}. Chạy start_api.bat. Chi tiết: {$error}"], JSON_UNESCAPED_UNICODE);
  exit;
}
http_response_code($http_code);
echo $response;
