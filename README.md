# FM八丈島 TV / HACHIJOJIMA TV

八丈島の映像を時間軸で編成する、GitHub Pages上の静的Webテレビです。サーバー、APIキー、npmは不要です。

## ローカル確認

`tv` ディレクトリで `python3 -m http.server 8000` を実行し、`http://localhost:8000` を開きます。これは開発確認用だけです。

## 編成を編集する

素材は `library.json`、編成ルールは `programming.json` に分かれています。ページはJSTの日付をseedに0:00〜24:00の番組表を一度生成し、全視聴者が同じ表を共有します。00:00 / 03:00 / 06:00 / 09:00 / 12:00 / 15:00 / 18:00 / 21:00 はソフトアンカーです。DAWN、SUNSET、EVENT LIVE、22:30 TOKYO RELAY、長尺枠を優先します。

`library.json` の `sources` へ通常素材を追加し、`catalogs.islandArchive` または `catalogs.nightMusic` へIDを加えます。VODの `duration` は動画の実時間（秒）です。夜の音楽はジャンル名ではなく `LONG PLAY`（フルアルバム／長尺ライブ）として編成し、`atomic: true` の作品はソフトアンカーで途中分断しません。

```json
{ "type": "vod", "youtubeId": "XXXXXXXXXXX", "programLabel": "HACHIJO ARCHIVE", "detail": "ISLAND DOCUMENT", "sourceTitle": "実際のYouTubeタイトル", "sourceChannel": "投稿元", "duration": 720, "atomic": true }
```

長尺音楽・ライブを追加する場合は、投稿元と埋め込み可否を確認したうえで `catalogs.nightMusic.LONG PLAY` にIDを追加します。番組画面では `LONG PLAY` と実際の作品名を表示します。

真のイベントLIVEは `programming.json` の `events` へ追加します。イベントはDAWN、SUNSET、固定アンカーより優先し、LIVEにはseekしません。

```json
{ "type":"event-live", "start":"2026-08-30T18:00:00+09:00", "end":"2026-08-30T20:30:00+09:00", "youtubeId":"XXXXXXXXXXX", "detail":"EVENT LIVE" }
```

八丈太鼓とAIlandleagueの過去LIVEアーカイブは `library.json` の `archivePools` にあります。どちらも通常動画タブではなく各チャンネルの `/streams` を起点に確認したアーカイブです。`youtubeId`、YouTube上で確認した実時間（秒）、年（太鼓の場合）を追加すると、日付seedによりアーカイブと開始位置を選びます。太鼓は1日4枠、AIlandleagueは1日0〜2枠です。

太鼓の重複ロック日数は固定値ではありません。各sourceの `floor(duration / 3600)` の合計から `usableBlockCount` を算出し、`theoreticalCycleDays = floor(usableBlockCount / 4)`、`hardCooldownDays = max(1, theoreticalCycleDays - 2)` として自動計算します。ブラウザのconsoleに当日の選択source・offsetと一緒に出力されます。

```json
{ "id":"taiko-2026", "youtubeId":"XXXXXXXXXXX", "duration":86400, "archiveYear":2026, "sourceTitle":"実際の配信タイトル", "sourceChannel":"24時間チャレンジ八丈太鼓" }
```

太陽連動枠、22:30のTOKYO RELAY、枠長は `programming.json` で調整します。変更をcommit・pushするとGitHub Pagesへ反映されます。

## 公開

GitHub Pagesは `main` ブランチの `/ (root)` を公開元に設定します。Custom domainは `tv.hachijojima.jp` に設定し、DNSには既存レコードに触れず `CNAME  tv  hachijojima.github.io` を追加します。`CNAME` ファイルも同ドメインをGitHub Pagesへ通知します。
