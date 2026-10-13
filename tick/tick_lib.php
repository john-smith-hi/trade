<?php
/**
 * Đọc CSV tick Exness từ data/GOLD/tick — không load cả file.
 */
declare(strict_types=1);

function tick_config_path(): ?string
{
    $cfg = __DIR__ . DIRECTORY_SEPARATOR . "config.php";
    if (!is_file($cfg)) {
        return null;
    }
    $data = include $cfg;
    if (!is_array($data) || empty($data["data_dir"])) {
        return null;
    }
    return rtrim((string) $data["data_dir"], "/\\");
}

function tick_data_dir(): string
{
    $fromCfg = tick_config_path();
    if ($fromCfg !== null && is_dir($fromCfg)) {
        return $fromCfg;
    }
    $candidates = [
        dirname(__DIR__) . DIRECTORY_SEPARATOR . "data" . DIRECTORY_SEPARATOR . "GOLD" . DIRECTORY_SEPARATOR . "tick",
    ];
    foreach ($candidates as $dir) {
        if (is_dir($dir)) {
            return $dir;
        }
    }
    throw new RuntimeException(
        "Không tìm thấy folder tick CSV. Copy config.example.php → config.php và đặt data_dir."
    );
}

function tick_list_files(): array
{
    $dir = tick_data_dir();
    $out = [];
    foreach (glob($dir . DIRECTORY_SEPARATOR . "Exness_XAUUSDm_*.csv") ?: [] as $path) {
        if (!is_file($path)) {
            continue;
        }
        $out[] = [
            "name" => basename($path),
            "size" => filesize($path),
            "mtime" => filemtime($path),
        ];
    }
    usort($out, fn($a, $b) => strcmp($a["name"], $b["name"]));
    return $out;
}

function tick_parse_utc(string $raw): ?DateTimeImmutable
{
    $s = trim($raw, " \t\n\r\0\x0B\"");
    if ($s === "") {
        return null;
    }
    if (str_ends_with(strtolower($s), "z")) {
        $s = substr($s, 0, -1);
    }
    $s = str_replace("T", " ", $s);
    if (strlen($s) < 19) {
        return null;
    }
    $fmt = "Y-m-d H:i:s";
    $micro = 0;
    if (strlen($s) > 19 && $s[19] === ".") {
        $frac = preg_replace("/\D/", "", substr($s, 20, 10));
        if ($frac !== "") {
            $micro = (int) substr(str_pad($frac, 6, "0"), 0, 6);
        }
        $s = substr($s, 0, 19);
    }
    $dt = DateTimeImmutable::createFromFormat($fmt, $s, new DateTimeZone("UTC"));
    if ($dt === false) {
        return null;
    }
    if ($micro > 0) {
        $dt = $dt->modify("+{$micro} microseconds");
    }
    return $dt;
}

function tick_vn_to_utc(string $dateYmd, string $timeHms): DateTimeImmutable
{
    $dt = DateTimeImmutable::createFromFormat(
        "Y-m-d H:i:s",
        $dateYmd . " " . $timeHms,
        new DateTimeZone("+07:00")
    );
    if ($dt === false) {
        throw new InvalidArgumentException("Ngày/giờ không hợp lệ.");
    }
    return $dt->setTimezone(new DateTimeZone("UTC"));
}

function tick_fmt_vn(DateTimeInterface $dt): string
{
    $local = $dt->setTimezone(new DateTimeZone("+07:00"));
    $base = $local->format("d/m/Y H:i:s");
    $micro = (int) $local->format("u");
    if ($micro > 0) {
        $base .= "." . rtrim(str_pad((string) $micro, 6, "0", STR_PAD_LEFT), "0");
    }
    return $base;
}

function tick_csv_path(int $year, int $month): string
{
    $name = sprintf("Exness_XAUUSDm_%04d_%02d.csv", $year, $month);
    $path = tick_data_dir() . DIRECTORY_SEPARATOR . $name;
    if (!is_file($path)) {
        throw new RuntimeException("Không có file {$name} trong " . tick_data_dir());
    }
    return $path;
}

function tick_extract_needle(DateTimeInterface $startUtc): string
{
    return $startUtc->format("Y-m-d H:i");
}

function tick_lines_with_needle(string $path, string $needle): array
{
    if (!is_file($path)) {
        return [];
    }
    $isWin = strtoupper(substr(PHP_OS, 0, 3)) === "WIN";
    if ($isWin) {
        $cmd = "findstr /C:" . escapeshellarg($needle) . " " . escapeshellarg($path);
    } else {
        $cmd = "grep -F " . escapeshellarg($needle) . " " . escapeshellarg($path) . " 2>/dev/null";
    }
    $out = [];
    $code = 0;
    if ($isWin) {
        exec($cmd, $out, $code);
        if ($code !== 0 && $code !== 1) {
            throw new RuntimeException("findstr lỗi (mã {$code}).");
        }
    } else {
        exec($cmd, $out, $code);
    }
    return array_values(array_filter($out, fn($ln) => trim($ln) !== ""));
}

function tick_query_range(
    string $dateYmd,
    string $fromTime,
    string $toTime,
    int $maxPoints = 8000
): array {
    $startUtc = tick_vn_to_utc($dateYmd, $fromTime);
    $endUtc = tick_vn_to_utc($dateYmd, $toTime);
    if ($endUtc < $startUtc) {
        throw new InvalidArgumentException("Thời gian bắt đầu sau thời gian kết thúc.");
    }
    $y = (int) $startUtc->format("Y");
    $m = (int) $startUtc->format("n");
    $path = tick_csv_path($y, $m);
    $needle = tick_extract_needle($startUtc);
    $lines = tick_lines_with_needle($path, $needle);
    $bid = [];
    $ask = [];
    $rows = [];
    $startMs = (int) ($startUtc->getTimestamp() * 1000);
    foreach ($lines as $line) {
        $row = str_getcsv($line);
        if (count($row) < 5) {
            continue;
        }
        $ts = tick_parse_utc($row[2]);
        if ($ts === null) {
            continue;
        }
        if ($ts < $startUtc || $ts > $endUtc) {
            continue;
        }
        $tMs = (int) ($ts->getTimestamp() * 1000) + (int) floor((int) $ts->format("u") / 1000);
        $sec = ($tMs - $startMs) / 1000.0;
        try {
            $b = (float) $row[3];
            $a = (float) $row[4];
        } catch (Throwable) {
            continue;
        }
        $bid[] = [$sec, $b];
        $ask[] = [$sec, $a];
        if (count($rows) < 200) {
            $rows[] = [
                "ts_vn" => tick_fmt_vn($ts),
                "bid" => $b,
                "ask" => $a,
                "spread" => round($a - $b, 6),
            ];
        }
    }
    $count = count($bid);
    if ($count > $maxPoints) {
        $step = (int) ceil($count / $maxPoints);
        $bid2 = [];
        $ask2 = [];
        for ($i = 0; $i < $count; $i += $step) {
            $bid2[] = $bid[$i];
            $ask2[] = $ask[$i];
        }
        $bid = $bid2;
        $ask = $ask2;
    }
    return [
        "file" => basename($path),
        "data_dir" => tick_data_dir(),
        "from_vn" => tick_fmt_vn($startUtc),
        "to_vn" => tick_fmt_vn($endUtc),
        "count" => $count,
        "bid" => $bid,
        "ask" => $ask,
        "rows" => $rows,
    ];
}

function tick_parse_date_vn(string $raw): string
{
    $s = trim($raw);
    if (!preg_match("/^(\d{2})\/(\d{2})\/(\d{4})$/", $s, $m)) {
        throw new InvalidArgumentException("Ngày phải dd/mm/yyyy.");
    }
    return sprintf("%04d-%02d-%02d", (int) $m[3], (int) $m[2], (int) $m[1]);
}

function tick_parse_time(string $raw, bool $end = false): string
{
    $s = trim($raw);
    if (preg_match("/^\d{2}:\d{2}$/", $s)) {
        $s .= $end ? ":59" : ":00";
    }
    if (!preg_match("/^\d{2}:\d{2}:\d{2}$/", $s)) {
        throw new InvalidArgumentException("Giờ phải HH:MM hoặc HH:MM:SS.");
    }
    return $s;
}
