# النشر الأوتوماتيكي — COMPUTER DZ (Facebook + Instagram Reels)

السكريبت `publish.py` ينشر الكرياتيف المعتمدين (الـ 30 اللي في جروب «كرياتيف») كـ Reels في صفحة Facebook وفي حساب Instagram تاع COMPUTER DZ، بالـ API الرسمي تاع Meta.

- **الرزنامة:** `calendar.json`، زوج في النهار (13:00 و 20:00، توقيت الجزائر).
- **الترتيب:** دورات. الفيديو 1 تاع كل منتج، ثم الفيديو 2 تاع كل منتج… حتى 5. المنتجات بنفس ترتيب «كرياتيف»: HP G9، Dell 3310، Dell 3380، NEC، Dell 3120، Dell 3190.
- **التشغيل:** GitHub Actions كل 15 دقيقة (`.github/workflows/autopost.yml`). الماك ما يلزمش يكون شاعل.
- **الفيديوهات:** في الفرع `autopost-media` (`media/`).
- **اللي تنشر:** يتسجل في `state.json`، فيه الرابط تاع كل منشور.

## الأمان

ما يتنشر والو إلا كي يكونو الزوج شروط هادو صحاح:

- **فايتة `AUTOPOST_ENABLED = true`**: تحطوها أنتوما في GitHub (Settings → Secrets and variables → Actions → Variables). تبدلوها لـ `false` ← يحبس النشر فوراً.
- **كل منشور فيه `"approved": true`**: ما يتحطش غير بعد ما تعتمدو الرزنامة.

الـ token:

- يتحط غير في GitHub Secrets (`META_TOKEN`).
- السكريبت ما يطبعوش، وما يحطوش في حتى رابط.
- ما تبعثوه لحتى واحد، حتى لـ Claude.

## الخطوات اللي تديروهم أنتوما (مرة وحدة)

### 1. تأكدو من الحسابات

1. في Meta Business Suite (business.facebook.com) ← Paramètres ← Comptes ← Comptes Instagram.
2. تأكدو بلي حساب Instagram تاع COMPUTER DZ هو **Professionnel** (Entreprise ولا Créateur)، ومربوط بصفحة COMPUTER DZ.

### 2. أخلقو تطبيق Meta

1. developers.facebook.com ← My Apps ← **Create app**.
2. الاسم: `COMPUTER DZ autopost`.
3. Use cases: **«Manage everything on your Page»** و **«Manage messaging & content on Instagram»**.
4. أربطو التطبيق بنفس الـ Business portfolio تاع COMPUTER DZ.
5. في App settings ← Basic: حطو **Privacy Policy URL** (صفحة الشروط ولا الخصوصية تاع المتجر) و Category، ومن بعد Save.
6. **App Mode ← Live.** في Development mode المنشورات يشوفوهم غير الناس اللي عندهم دور في التطبيق، والعباد ما يشوفوهمش.
   - إذا Meta طلبت App Review باش تحطو Live، قولولي قبل ما تكملو.

### 3. أخلقو System User و token

1. business.facebook.com/settings ← Utilisateurs ← **Utilisateurs système** ← Ajouter.
2. الاسم: `autopost`. الدور: **Admin**.
3. **Ajouter des ressources**، وعطوه هادو:
   - التطبيق `COMPUTER DZ autopost` (contrôle total).
   - صفحة COMPUTER DZ (contrôle total، ولا على الأقل «Créer du contenu»).
   - حساب Instagram تاع COMPUTER DZ.
4. **Générer un token**:
   - التطبيق: `COMPUTER DZ autopost`.
   - Expiration: **Jamais**.
   - الصلاحيات: `pages_show_list`، `pages_read_engagement`، `pages_manage_posts`، `instagram_basic`، `instagram_content_publish`، `business_management`.
5. انسخو الـ token. ما تبعثوهش لحتى واحد.

### 4. حطوه في GitHub

1. الريبو `computerdz-ads` ← **Settings** ← **Secrets and variables** ← **Actions**.
2. **Secrets** ← New repository secret:
   - Name: `META_TOKEN`
   - Value: الـ token
3. **Variables** ← New repository variable:
   - `AUTOPOST_ENABLED` = `false` (تولي `true` كي تعتمدو).
4. ما يلزمش `META_PAGE_ID`: كي يكون System User عندو صفحة وحدة، السكريبت يلقاها وحدو.

### 5. الفحص

1. قولو لـ Claude «حطيت الـ token».
2. يشغّل `check` (Actions ← autopost ← Run workflow ← mode = check). هذا يقرا برك، ما ينشر والو.
3. يبين:
   - لمن تابع الـ token.
   - الصلاحيات.
   - الصفحة وحساب IG.
   - قداش بقى من الحد اليومي تاع IG.

### 6. أول منشور

1. تعتمدو الرزنامة: Claude يحط `"approved": true`.
2. تحطو `AUTOPOST_ENABLED = true`.
3. أول منشور يخرج في وقتو.
4. تفقدوه من حساب آخر (ماشي admin) باش تتأكدو بلي العباد يشوفوه.

## باش تبدلو حاجة

- **تحبسو كلش:** `AUTOPOST_ENABLED = false`.
- **تحبسو منشور واحد:** في `calendar.json` حطو `"enabled": false`.
- **تبدلو الوقت ولا الكابشن:** بدلو `publish_at` (`YYYY-MM-DD HH:MM`) ولا `caption` في `calendar.json`.
- **تشوفو الرزنامة:** Actions ← Run workflow ← mode = plan.

## واش يصرا كي تطيح حاجة

- **منصة وحدة طاحت** (مثلاً IG): يعاود غير هي في التشغيل الجاي، حتى 3 مرات. FB ما يتعاودش.
- **GitHub حبس مدة:** يكمل من وين حبس، فيديو واحد كل 3 سوايع على الأقل، وغير بين 09:00 و 23:00.
- **أي فشل:** التشغيل يولي أحمر، و GitHub يبعث إيمايل لصاحب الريبو.

## حدود Meta (docs، نوفمبر 2026)

- **Facebook Reels:** 30 منشور كل 24 ساعة، الفيديو من 3 حتى 90 ثانية، 9:16.
- **Instagram:** 50 منشور كل 24 ساعة.
- **فيديوهاتنا:** من 56 حتى 77 ثانية، 1080×1920، H.264، AAC 48 kHz.
