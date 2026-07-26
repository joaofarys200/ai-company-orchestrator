# AirLLM 3.0.1 / Qwen 3.5 compatibility investigation

## Immediate failure

The installed code path is:

1. `airllm.auto_model.AutoModel.from_pretrained()` selects
   `AirLLMBaseModel` because `Qwen3_5MoeForConditionalGeneration` is absent from
   `ARCH_OVERRIDES`.
2. `AirLLMBaseModel.__init__()` configures the generic prefix `model.layers` and
   calls `find_or_create_local_splitted_path()`.
3. That function downloads repository metadata while excluding `*.safetensors`
   and `*.bin`, then calls `split_and_save_layers()`.
4. `split_and_save_layers()` reads `model.safetensors.index.json` and executes
   the list comprehension at installed `airllm/utils.py:237`.

A metadata-only reproduction using the real index-key shape produces:

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "...\venv\Lib\site-packages\airllm\utils.py", line 237, in split_and_save_layers
    n_layers = len(set([int(k[len(layer_names['layer_prefix']):].split('.')[1]) for k in index.keys() if layer_names['layer_prefix'] in k]))
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: invalid literal for int() with base 10: 'layers'
```

For
`k = "model.language_model.layers.0.mlp.experts.gate_up_proj"` and
`layer_prefix = "model.layers"`, the substring test passes even though the
prefix is not at the start. Slicing at `len("model.layers")` and then selecting
`split('.')[1]` yields the exact value `"layers"`.

This happens while interpreting state-dict parameter names from the index to
identify numbered layers. No weight file has been interpreted and no AirLLM
layer shard has yet been created.

## Support evidence

`airllm/auto_model.py` 3.0.1 contains explicit overrides for legacy QWen,
ChatGLM, Baichuan, and InternLM layouts. It has no override for Qwen2, Qwen3,
Qwen3 MoE, or Qwen 3.5. A Qwen2 subclass exists but is not selected by the
override table and does not change the generic layer names.

The generic path delegates `forward()` and `generate()` to Transformers, which
makes a text-only experiment plausible after correcting the module paths. It
does not prove execution. The Qwen 3.5 checkpoint also contains:

- `model.visual.*` parameters;
- `mtp.*` parameters;
- MoE parameters below numbered decoder blocks;
- `linear_attn.*` Gated DeltaNet parameters below numbered decoder blocks.

The experimental patch recognizes all these families so that an unknown key is
never silently dropped. It streams only the nested language-model embedding,
40 numbered decoder blocks, final norm, and `lm_head`, matching the generic
AirLLM hook model. Visual and MTP execution remain outside its scope.

The complete official 187 kB index was validated without downloading weight
files. Its 1,811 keys classified as 690 language-block parameters, one
embedding, one final norm, one `lm_head`, 333 visual parameters, and 785 MTP
parameters. No key remained unclassified. The 1,118 explicitly non-streamed
visual/MTP parameters are the principal reason this patch is not proof of full
model compatibility.

## Patch boundary

The patch is disabled by default and modifies no installed file. When enabled,
it downloads only `model.safetensors.index.json`, validates the complete key
set and contiguous declared layer indices, emits an experimental warning, and
registers an in-memory subclass with these paths:

```text
embed        model.language_model.embed_tokens
layer_prefix model.language_model.layers
norm         model.language_model.norm
lm_head      lm_head
```

Passing this parser boundary is not evidence that Qwen 3.5 MoE, Gated DeltaNet,
multimodal processing, MTP, 4-bit compression, or end-to-end generation works
under AirLLM 3.0.1.
