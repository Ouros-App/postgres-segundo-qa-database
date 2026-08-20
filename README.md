# Postgres Segundo QA Database

<!-- REPO-METADATA:START -->
<div align="center">

[![Repo Size](https://img.shields.io/github/repo-size/Ouros-App/postgres-segundo-qa-database?style=flat-square&label=REPO%20SIZE)](https://github.com/Ouros-App/postgres-segundo-qa-database)
[![Languages](https://img.shields.io/github/languages/count/Ouros-App/postgres-segundo-qa-database?style=flat-square&label=LANGUAGES)](https://github.com/Ouros-App/postgres-segundo-qa-database/languages)
[![Forks](https://img.shields.io/github/forks/Ouros-App/postgres-segundo-qa-database?style=flat-square&label=FORKS)](https://github.com/Ouros-App/postgres-segundo-qa-database/network/members)
[![Issues](https://img.shields.io/github/issues/Ouros-App/postgres-segundo-qa-database?style=flat-square&label=ISSUES)](https://github.com/Ouros-App/postgres-segundo-qa-database/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/Ouros-App/postgres-segundo-qa-database?style=flat-square&label=PULL%20REQUESTS)](https://github.com/Ouros-App/postgres-segundo-qa-database/pulls)

</div>
<!-- REPO-METADATA:END -->

Template de banco PostgreSQL para o ambiente de QA, com schema SQL local aplicado por um script Python e controle de versões por commit.

## Status e escopo

O repositório configura o projeto postgres-segundo-qa-database. O arquivo config.yaml aponta para sql/, usa a tabela controle_versoes e agenda a aplicação única de banco_ouros_fisico.sql.

## Principais componentes

- scripts/apply_sql.py: carrega as variáveis de .env, expande config.yaml, garante a role e o banco e aplica os SQL.
- sql/versionamento.sql: cria a tabela controle_versoes.
- sql/banco_ouros_fisico.sql: cria o schema inicial com tabelas como addresses, enterprises, farms, tips, categories, reviews, metas e registros de água/energia, além das relações entre esses dados.
- A tabela controle_scripts_sql registra checksum, commit e data de execução dos scripts.
- config.yaml define execution_order com modo once para banco_ouros_fisico.sql.
- GitHub Actions validam o scaffold e os SQL; o workflow de main aplica o script após push.

## Pré-requisitos

- Python com acesso para instalar as dependências de requirements.txt.
- Um servidor PostgreSQL acessível.
- Credenciais para conexão bootstrap e para o usuário dono do banco.

Dependências fixadas no repositório:

- psycopg2-binary 2.9.9
- PyYAML 6.0.2
- python-dotenv 1.0.1

## Instalação e configuração

Linux:

~~~bash
cp .env.example .env
python -m pip install -r requirements.txt
~~~

Windows PowerShell:

~~~powershell
Copy-Item .env.example .env
python -m pip install -r requirements.txt
~~~

Configure no .env:

| Variável | Finalidade |
| --- | --- |
| POSTGRES_HOST | Host do PostgreSQL. |
| POSTGRES_PORT | Porta do PostgreSQL. |
| POSTGRES_DB | Banco da aplicação. |
| POSTGRES_USER | Usuário dono do banco. |
| POSTGRES_PASSWORD | Senha do usuário dono. |
| POSTGRES_ROOT_DB | Banco usado na conexão bootstrap. |
| POSTGRES_ROOT_USER | Usuário bootstrap. |
| POSTGRES_ROOT_PASSWORD | Senha do usuário bootstrap. |

As variáveis devem corresponder aos placeholders usados por config.yaml. Não versione .env.

## Execução

Na raiz do repositório:

~~~bash
python scripts/apply_sql.py
~~~

O script identifica o commit por GITHUB_SHA ou pelo Git local, garante a role e o banco configurados, cria a tabela de versionamento, aplica os SQL elegíveis e registra a execução em controle_versoes.

A configuração atual usa sql/versionamento.sql como schema de versionamento e executa sql/banco_ouros_fisico.sql com modo once. Como esse modo registra o script, execuções posteriores o ignoram enquanto a entrada continuar registrada.

## Testes e qualidade

Existe um teste unitário em tests/test_apply_sql.py. Para executá-lo localmente:

~~~bash
python -m unittest discover -s tests -v
~~~

O workflow CI/CD atual valida a presença dos arquivos essenciais, a referência dos SQL em config.yaml e bloqueia TRUNCATE e DROP DATABASE/TABLE/SCHEMA. Ele não executa a suíte unitária no CI. O workflow Apply SQL On Main instala as dependências e executa scripts/apply_sql.py após push em main.

## Estrutura do projeto

~~~text
sql/
  banco_ouros_fisico.sql
  versionamento.sql
scripts/
  apply_sql.py
tests/
  test_apply_sql.py
config.yaml
.env.example
requirements.txt
.github/workflows/
  ci-cd.yml
  apply-sql-on-main.yml
~~~

## Contribuição

Inclua alterações de schema em arquivos SQL, atualize database.execution_order quando necessário e valide o teste local e os workflows antes de abrir uma pull request.

## Licença

Este projeto está sob a licença MIT. Consulte LICENSE para o texto completo.


## Principais contribuidores

<!-- CONTRIBUTORS:START -->
- [@Nicolas25vlad](https://github.com/Nicolas25vlad) — 6 contribuições
- [@LucasRamosDeCarvalho](https://github.com/LucasRamosDeCarvalho) — 2 contribuições
<!-- CONTRIBUTORS:END -->

> Atualizado automaticamente semanalmente pelo workflow de metadados do README.
