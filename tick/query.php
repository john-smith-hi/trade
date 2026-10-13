<?php
header_remove("X-Powered-By");
header("Content-Type: application/json; charset=utf-8");
header("X-Content-Type-Options: nosniff");
header("Cache-Control: no-store");

ini_set("display_errors", "0");
ini_set("max_execution_time", "120");

require __DIR__ . DIRECTORY_SEPARATOR . "tick_lib.php";

function fail(int $code, string $msg): void
{
    http_response_code($code);
    echo json_encode(["error" => $msg], JSON_UNESCAPED_UNICODE);
    exit;
}

try {
    if (isset($_GET["files"])) {
        echo json_encode([
            "ok" => true,
            "dir" => tick_data_dir(),
            "files" => tick_list_files(),
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }
    $date = tick_parse_date_vn((string) ($_GET["date"] ?? ""));
    $from = tick_parse_time((string) ($_GET["from"] ?? "19:30:00"), false);
    $to = tick_parse_time((string) ($_GET["to"] ?? "19:31:00"), true);
    $result = tick_query_range($date, $from, $to);
    echo json_encode(["ok" => true] + $result, JSON_UNESCAPED_UNICODE);
} catch (InvalidArgumentException $e) {
    fail(400, $e->getMessage());
} catch (Throwable $e) {
    fail(500, $e->getMessage());
}
