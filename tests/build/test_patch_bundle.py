import unittest

from neo.build.patch_bundle import (
    force_show_all_sensitive_tweet_media_in_smali,
    force_show_sensitive_media_in_smali,
)


class PatchBundleTests(unittest.TestCase):
    def test_force_show_sensitive_media_rewrites_method_to_return_true(self) -> None:
        smali = """\
.class public Lapp/morphe/extension/twitter/Pref;

.method public static showSensitiveMedia()Z
    .locals 1

    .line 69
    sget-object v0, Lapp/morphe/extension/twitter/settings/Settings;->TIMELINE_SHOW_SENSITIVE_MEDIA:Lapp/morphe/extension/shared/settings/BooleanSetting;

    invoke-static {v0}, Lapp/morphe/extension/twitter/Utils;->getBooleanPerf(Lapp/morphe/extension/shared/settings/BooleanSetting;)Ljava/lang/Boolean;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/Boolean;->booleanValue()Z

    move-result v0

    return v0
.end method

.method public static showSourceLabel()Z
    .locals 1
.end method
"""

        rewritten = force_show_sensitive_media_in_smali(smali)

        self.assertIn("const/4 v0, 0x1", rewritten)
        self.assertIn(".method public static showSourceLabel()Z", rewritten)
        self.assertNotIn("TIMELINE_SHOW_SENSITIVE_MEDIA", rewritten)

    def test_force_show_sensitive_media_is_idempotent(self) -> None:
        smali = """\
.method public static showSensitiveMedia()Z
    .locals 1

    const/4 v0, 0x1

    return v0
.end method
"""

        self.assertEqual(force_show_sensitive_media_in_smali(smali), smali)

    def test_force_show_sensitive_media_requires_target_method(self) -> None:
        with self.assertRaises(RuntimeError):
            force_show_sensitive_media_in_smali(".method public static other()V\n.end method\n")

    def test_force_show_all_sensitive_tweet_media_returns_false(self) -> None:
        smali = """\
.class public final Lcom/twitter/tweetview/core/n;

.method public static final a(Lcom/twitter/model/core/e;ZLcom/twitter/tweetview/core/x$a;)Z
    .param p0    # Lcom/twitter/model/core/e;
    .end param
    .param p2    # Lcom/twitter/tweetview/core/x$a;
    .end param
    .annotation build Lkotlin/jvm/JvmOverloads;
    .end annotation

    .locals 2

    invoke-virtual {p0}, Lcom/twitter/model/core/e;->F0()Z

    move-result p0

    return p0
.end method
"""

        rewritten = force_show_all_sensitive_tweet_media_in_smali(smali)

        self.assertIn("const/4 v0, 0x0", rewritten)
        self.assertIn(".annotation build Lkotlin/jvm/JvmOverloads;", rewritten)
        self.assertNotIn("invoke-virtual {p0}, Lcom/twitter/model/core/e;->F0()Z", rewritten)

    def test_force_show_all_sensitive_tweet_media_is_idempotent(self) -> None:
        smali = """\
.method public static final a(Lcom/twitter/model/core/e;ZLcom/twitter/tweetview/core/x$a;)Z
    .annotation build Lkotlin/jvm/JvmOverloads;
    .end annotation

    .locals 1

    const/4 v0, 0x0

    return v0
.end method
"""

        self.assertEqual(force_show_all_sensitive_tweet_media_in_smali(smali), smali)

    def test_force_show_all_sensitive_tweet_media_requires_target_method(self) -> None:
        with self.assertRaises(RuntimeError):
            force_show_all_sensitive_tweet_media_in_smali(
                ".method public static other()V\n.end method\n"
            )
