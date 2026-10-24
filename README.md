# FM八丈島 TV β3

公開URL: https://tv.hachijojima.jp/

## 他サイトへの埋め込み

`https://tv.hachijojima.jp/embed.html` は現在の編成を再生する専用プレーヤーです。初回はミュートで再生し、音声・全画面ボタンを表示します。サイズは埋め込み先で指定します。操作欄は映像の下端に重ね、映像の高さを削りません。16:9の動画には、下記の16:9指定を使ってください。

```html
<iframe
  src="https://tv.hachijojima.jp/embed.html"
  title="FM八丈島テレビ"
  style="display:block;width:100%;aspect-ratio:16/9;border:0"
  allow="autoplay; fullscreen"
  allowfullscreen
></iframe>
```

固定サイズにする場合は `style="border:0" width="640" height="360"` を指定してください。YouTubeプレーヤーの表示領域を確保するため、高さは200px以上を推奨します。自動再生や全画面の可否は埋め込み先とブラウザの設定にも依存します。

PUBLICはSupabaseの`schedule_items`からNOW/NEXTだけを読み、YouTube公式IFrame Playerで再生します。編成生成はPUBLICでは行いません。

通常familyは`music`、`hachijo_taiko`、`power_push`、`sports`、`hachijo_picks`です。SPECIALは`island_view`と`tokyo_relay`です。

## Dashboard

`/dashboard.html`で管理者ログイン後、Libraryの追加・編集・削除と`REGENERATE NOW`ができます。追加・編集・削除は自動再生成しません。

## 編成

`public.regenerate_schedule()`は現在時刻から最低72時間を生成します。通常cycleは `MUSIC → HACHIJO TAIKO → SPORTS → HACHIJO PICKS` 固定です。DAWN/SUNSETと22:30 JSTのTOKYO RELAYのみがhard cutです。毎日03:00 JSTは`pg_cron`が同じfunctionを実行します。

## DB

`supabase/migrations/0002_clean_rebuild.sql`がclean baseline、`0003_cron_regenerate_wrapper.sql`がcron wrapperです。正しいLibrary snapshotは`supabase/clean-library-seed.sql`です。
