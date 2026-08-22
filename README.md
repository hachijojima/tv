# FM八丈島 TV / HACHIJOJIMA TV

八丈島の映像を時間軸で編成する、GitHub Pages上の静的Webテレビです。サーバー、APIキー、npmは不要です。

## ローカル確認

`tv` ディレクトリで `python3 -m http.server 8000` を実行し、`http://localhost:8000` を開きます。これは開発確認用だけです。

## 動画を1本追加する

`schedule.json` の `programs` 配列へ追加します。VODの `duration` は動画の実時間（秒）で、アクセス時には番組内の経過時間から途中再生します。

```json
{ "type": "vod", "youtubeId": "XXXXXXXXXXX", "title": "番組名", "channel": "投稿元チャンネル", "duration": 720, "enabled": true }
```

LIVEはYouTube動画IDを直接指定し、`slotDuration` に番組表上の放送枠（秒）を指定します。LIVEにはseekしません。

```json
{ "type": "live", "youtubeId": "XXXXXXXXXXX", "title": "底土港 LIVE", "channel": "投稿元チャンネル", "slotDuration": 1800, "enabled": true }
```

`enabled: false` で編成から外せます。変更をcommit・pushするとGitHub Pagesへ反映されます。

## 公開

GitHub Pagesは `main` ブランチの `/ (root)` を公開元に設定します。Custom domainは `tv.hachijojima.jp` に設定し、DNSには既存レコードに触れず `CNAME  tv  hachijojima.github.io` を追加します。`CNAME` ファイルも同ドメインをGitHub Pagesへ通知します。
