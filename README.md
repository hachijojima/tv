# FM八丈島 TV β3

公開URL: https://tv.hachijojima.jp/

PUBLICはSupabaseの`schedule_items`からNOW/NEXTだけを読み、YouTube公式IFrame Playerで再生します。編成生成はPUBLICでは行いません。

通常familyは`music`、`hachijo_taiko`、`sports`、`hachijo_picks`です。SPECIALは`island_view`と`tokyo_relay`です。

## Dashboard

`/dashboard.html`で管理者ログイン後、Libraryの追加・編集・削除と`REGENERATE NOW`ができます。追加・編集・削除は自動再生成しません。

## 編成

`public.regenerate_schedule()`は現在時刻から最低72時間を生成します。通常cycleは `MUSIC → HACHIJO TAIKO → SPORTS → HACHIJO PICKS` 固定です。DAWN/SUNSETと22:30 JSTのTOKYO RELAYのみがhard cutです。毎日03:00 JSTは`pg_cron`が同じfunctionを実行します。

## DB

`supabase/migrations/0002_clean_rebuild.sql`がclean baseline、`0003_cron_regenerate_wrapper.sql`がcron wrapperです。正しいLibrary snapshotは`supabase/clean-library-seed.sql`です。
