# TODO

## Line-Index 分代（Epoch）压缩

按行被发现的次序分代，current/ text + epoch_NNN/ gzip，解决行索引进 git 的体积问题。

详见 `ref/spec/line-hash-compaction.md` 末尾。
