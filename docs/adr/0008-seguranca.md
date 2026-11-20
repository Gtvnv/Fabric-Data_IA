# 0008. Segurança: identidades, segredos, proteção de dados e rede
Status: aceito
Data: 2026-11-20

## Contexto

A plataforma usa credenciais de fontes de dados, de service principals para provisionamento e implantação, e manipula dados pessoais sintéticos que devem seguir práticas reais. O repositório é versionado e não pode conter segredos. Os acessos devem seguir mínimo privilégio e deixar trilha de auditoria.

## Decisão

- Segredos: somente no Azure Key Vault (conexões de ingestão por linked services) e nos segredos do repositório de CI. Nenhum segredo no código ou na configuração versionada (`.env.example` só tem nomes e valores de exemplo). A varredura gitleaks no PR e um teste do repositório verificam isso.
- Identidades: Entra ID para pessoas, por grupos mapeados às funções de workspace. Service principals separados para provisionamento e deploy, com permissão mínima e por ambiente. Preferir identidade gerenciada, quando disponível, para acesso ao Key Vault.
- Proteção dos dados: classificação de sensibilidade em todas as colunas, mascaramento dinâmico (DDM) nas confidenciais, RLS por loja no modelo semântico e exclusão de PII direta das features de ML (ADR 0005 e 0006). Criptografia em repouso e em trânsito, com as configurações padrão do Fabric e do Azure.
- Falha segura: se o Key Vault estiver indisponível, a execução da entidade termina sem acessar a origem.
- Logs e alertas: nunca registram valores de segredo ou de PII. A auditoria de acessos negados vai para tabela consultável.
- Dados: sintéticos, com e-mails em `example.com` e `example.org`, telefones fictícios e documentos com dígito verificador inválido.

## Alternativas consideradas

- Segredos em variáveis de ambiente ou em arquivos de configuração versionados e cifrados: simples de usar, mas expõem a chave de decifração e dificultam a rotação e a auditoria.
- Autenticação por chave ou senha de SQL nas conexões, sem Entra ID: funciona em qualquer cliente, mas dificulta a rotação e o controle central.
- Um único service principal com permissão ampla em todos os ambientes: menos configuração, mas um vazamento comprometeria dev, test e prod.
- Isolamento por rede privada (private link e gateway) em todos os ambientes: reduz a exposição, mas aumenta o custo e a complexidade para uma plataforma de referência com dados sintéticos.

## Consequências

- Rotação e auditoria de segredos ficam centralizadas no Key Vault, e a ingestão depende da disponibilidade dele.
- Um service principal por ambiente exige mais configuração, mas limita o impacto de vazamento.
- Rede pública com identidade forte é aceitável apenas para dados sintéticos. Dados reais exigem reavaliar a rede privada em novo ADR.
- O DDM só protege consultas feitas pelo Warehouse e pelo SQL endpoint, então o acesso direto ao OneLake precisa ser limitado por papel.
