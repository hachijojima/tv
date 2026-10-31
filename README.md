# FM八丈島 TV β3

公開URL: https://tv.hachijojima.jp/

## 他サイトへの埋め込み

埋め込みの読み込みもトップページのアクセス累計（直近7日間）に加算します。同一のセッションストレージ内では日本時間の同日中は重複加算しません。ブラウザが埋め込みのストレージ利用を制限する場合も加算は行いますが、再読み込み時の重複防止はできません。

`https://tv.hachijojima.jp/embed.html` は現在の編成を再生する専用プレーヤーです。初回はミュートで再生します。操作欄は映像の下に44pxの高さで配置し、映像には重ねません。埋め込み全体の高さは「幅 × 9 ÷ 16 ＋ 44px」にしてください。以前のiframe全体を16:9にするコードからは差し替えが必要です。

幅に追従する埋め込み（映像16:9＋操作欄44px）：

```html
<div style="position:relative;width:100%;height:0;padding-top:calc(56.25% + 44px)">
  <iframe
    src="https://tv.hachijojima.jp/embed.html"
    title="FM八丈島テレビ"
    style="position:absolute;inset:0;display:block;width:100%;height:100%;border:0"
    allow="autoplay; fullscreen"
    allowfullscreen
  ></iframe>
</div>
```

固定サイズなら、映像640×360pxに操作欄44pxを足して以下を使います。

```html
<iframe
  src="https://tv.hachijojima.jp/embed.html"
  title="FM八丈島テレビ"
  width="640"
  height="404"
  style="display:block;border:0"
  allow="autoplay; fullscreen"
  allowfullscreen
></iframe>
```

YouTubeプレーヤーの表示領域を確保するため、全体の高さは244px以上を推奨します。元の動画に黒帯が含まれる場合や動画の縦横比が16:9と異なる場合は、黒帯が残ることがあります。自動再生や全画面の可否は埋め込み先とブラウザの設定にも依存します。

PUBLICはSupabaseの`schedule_items`からNOW/NEXTだけを読み、YouTube公式IFrame Playerで再生します。編成生成はPUBLICでは行いません。

通常familyは`music`、`hachijo_taiko`、`power_push`、`sports`、`hachijo_picks`です。SPECIALは`island_view`と`tokyo_relay`です。

## Dashboard

`/dashboard.html`で管理者ログイン後、Libraryの追加・編集・削除と`REGENERATE NOW`ができます。追加・編集・削除は自動再生成しません。

## 編成

`public.regenerate_schedule()`は現在時刻から最低72時間を生成します。通常cycleは `MUSIC → HACHIJO TAIKO → SPORTS → HACHIJO PICKS` 固定です。DAWN/SUNSETと22:30 JSTのTOKYO RELAYのみがhard cutです。毎日03:00 JSTは`pg_cron`が同じfunctionを実行します。

## DB

`supabase/migrations/0002_clean_rebuild.sql`がclean baseline、`0003_cron_regenerate_wrapper.sql`がcron wrapperです。正しいLibrary snapshotは`supabase/clean-library-seed.sql`です。
