# FM八丈島 TV / HACHIJOJIMA TV

八丈島の映像を時間軸で編成する、GitHub Pages上の静的Webテレビです。サーバー、APIキー、npmは不要です。

## ローカル確認

`tv` ディレクトリで `python3 -m http.server 8000` を実行し、`http://localhost:8000` を開きます。これは開発確認用だけです。

## 編成を編集する

素材は `library.json`、編成ルールは `programming.json` に分かれています。ページはJSTの日付をseedに0:00〜24:00の番組表を一度生成し、全視聴者が同じ表を共有します。

`library.json` の `sources` へ通常素材を追加します。VODの `duration` は動画の実時間（秒）です。

```json
{ "type": "vod", "youtubeId": "XXXXXXXXXXX", "title": "番組名", "channel": "投稿元チャンネル", "duration": 720, "enabled": true }
```

LIVEはYouTube動画IDを直接指定し、`slotDuration` に番組表上の放送枠（秒）を指定します。LIVEにはseekしません。

```json
{ "type": "live", "youtubeId": "XXXXXXXXXXX", "title": "底土港 LIVE", "channel": "投稿元チャンネル", "slotDuration": 1800, "enabled": true }
```

八丈太鼓の過去LIVEアーカイブは、同ファイルの `taikoArchivePool` に追加します。`youtubeId`、実時間（秒）、年を登録すると、1日2回の枠で日付seedによりアーカイブと開始位置を選びます。

```json
{ "id":"taiko-2026", "youtubeId":"XXXXXXXXXXX", "duration":86400, "archiveYear":2026, "sourceChannel":"24時間チャレンジ八丈太鼓" }
```

太陽連動枠、22:30のTOKYO RELAY、枠長は `programming.json` で調整します。変更をcommit・pushするとGitHub Pagesへ反映されます。

## 公開

GitHub Pagesは `main` ブランチの `/ (root)` を公開元に設定します。Custom domainは `tv.hachijojima.jp` に設定し、DNSには既存レコードに触れず `CNAME  tv  hachijojima.github.io` を追加します。`CNAME` ファイルも同ドメインをGitHub Pagesへ通知します。
