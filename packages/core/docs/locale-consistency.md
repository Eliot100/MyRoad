# Locale consistency rule

Platform **UI language** and path **explanations** must match the learner's UI locale.
Learning **content tokens** (vocab being taught) stay in the path's `content_locale`.

- UI in Hebrew + English-learning path → Hebrew chrome/explanations; English words only
  in `body_content` / `speak_text` / choice labels that are the target vocab.
- Switching UI language switches shell + explanation strings; content tokens stay.

Enforced by schema fields + `myroad_core.content.locale_rules.validate_locale_consistency`
(CI via pytest).
