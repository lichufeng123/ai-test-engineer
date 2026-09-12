# 批量导入导出示例

该示例展示如何把导入测试数据声明交给通用数据工厂。示例经过脱敏，不包含内部域名、账号和真实题目。

```bash
../../bin/ai-test data-generate \
  --spec fixture-spec.json \
  --output ./generated
```

生成后将 `fixture_manifest.json` 中的fixture ID绑定到现有正式测试用例Case-ID，再由Web或App执行器完成导入和业务回读。
