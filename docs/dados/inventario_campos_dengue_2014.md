# Inventário de campos: Dengue 2013 e 2014

Fonte: [Dicionário de dados - Dengue](dicionario_dados_dengue.pdf), Ministério da Saúde, e cabeçalhos dos CSVs anuais baixados do [Portal de Dados Abertos do SUS](https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue).

Cada **linha do CSV bruto é uma notificação**; cada coluna é um campo. A tabela abaixo lista todas as 121 colunas do arquivo de 2014, na ordem em que aparecem. A indicação de 2013 significa somente que a coluna existe nos dois arquivos, não que seus códigos possuam o mesmo significado.

| Nº no CSV 2014 | Campo | No CSV 2013? | Nome no dicionário (página) |
|---:|---|:---:|---|
| 1 | `TP_NOT` | sim | Tipo de Notificação (p. 1, item 1) |
| 2 | `ID_AGRAVO` | sim | Agravo (p. 1, item 2) |
| 3 | `DT_NOTIFIC` | sim | Data da Notificação (p. 1, item 3) |
| 4 | `SEM_NOT` | sim | Semana epidemiológica da notificação (campo interno) (p. 1, item 4) |
| 5 | `NU_ANO` | sim | Ano da Notificação (p. 2, item 5) |
| 6 | `SG_UF_NOT` | sim | UF de Notificação (p. 2, item 6) |
| 7 | `ID_MUNICIP` | sim | Município de Notificação (p. 2, item 7) |
| 8 | `ID_REGIONA` | sim | Regional (p. 2, item 8) |
| 9 | `ID_UNIDADE` | sim | Unidade de saúde ou outra fonte notificadora (p. 2, item 9) |
| 10 | `DT_SIN_PRI` | sim | Data dos primeiros sintomas / Diagnóstico (p. 2, item 10) |
| 11 | `SEM_PRI` | sim | Semana epidemiológica dos primeiros sintomas/ diagnósticos. (campo interno) (p. 3, item 11) |
| 12 | `ANO_NASC` | não | Ano de nascimento (p. 3, item 12) |
| 13 | `NU_IDADE_N` | sim | Idade (p. 3, item 13) |
| 14 | `CS_SEXO` | sim | Sexo (p. 3, item 14) |
| 15 | `CS_GESTANT` | sim | Gestante (p. 4, item 15) |
| 16 | `CS_RACA` | sim | Raça/Cor (p. 4, item 16) |
| 17 | `CS_ESCOL_N` | sim | Escolaridade (p. 5, item 17) |
| 18 | `SG_UF` | sim | UF (p. 5, item 18) |
| 19 | `ID_MN_RESI` | sim | Município de residência (p. 5, item 19) |
| 20 | `ID_RG_RESI` | sim | Regional de Saúde (p. 6, item 20) |
| 21 | `ID_PAIS` | sim | País (se residente fora do Brasil) (p. 6, item 21) |
| 22 | `DT_INVEST` | sim | Data da investigação (p. 6, item 22) |
| 23 | `ID_OCUPA_N` | sim | Ocupação/ramo de atividade econômica (p. 6, item 23) |
| 24 | `FEBRE` | não | Sinais clínicos (Febre) (p. 6, item 24) |
| 25 | `MIALGIA` | não | Sinais clínicos (Mialgia) (p. 6, item 25) |
| 26 | `CEFALEIA` | não | Sinais clínicos (Cefaleia) (p. 6, item 26) |
| 27 | `EXANTEMA` | não | Sinais clínicos (Exantema) (p. 6, item 27) |
| 28 | `VOMITO` | não | Sinais clínicos (Vômito) (p. 6, item 28) |
| 29 | `NAUSEA` | não | Sinais clínicos (Náusea) (p. 6, item 29) |
| 30 | `DOR_COSTAS` | não | Sinais clínicos (Dor nas costas) (p. 6, item 30) |
| 31 | `CONJUNTVIT` | não | Sinais clínicos (Conjuntivite) (p. 6, item 31) |
| 32 | `ARTRITE` | não | Sinais clínicos (Artrite) (p. 6, item 32) |
| 33 | `ARTRALGIA` | não | Sinais clínicos (Artralgia (p. 6, item 33) |
| 34 | `PETEQUIA_N` | não | Sinais clínicos (Petéquias) (p. 7, item 34) |
| 35 | `LEUCOPENIA` | não | Sinais clínicos (Leucopenia) (p. 7, item 35) |
| 36 | `LACO` | não | Sinais clínicos (Prova do laço) (p. 7, item 36) |
| 37 | `DOR_RETRO` | não | Sinais clínicos (Dor retroorbital) (p. 7, item 37) |
| 38 | `DIABETES` | não | Doenças préexistentes (Diabetes) (p. 7, item 38) |
| 39 | `HEMATOLOG` | não | Doenças préexistentes (Doenças hematológicas) (p. 7, item 39) |
| 40 | `HEPATOPAT` | não | Doenças préexistentes (Hepatopatias) (p. 7, item 40) |
| 41 | `RENAL` | não | Doenças préexistentes (Doença renal crônica) (p. 7, item 41) |
| 42 | `HIPERTENSA` | não | Doenças préexistentes (Hipertensão arterial) (p. 7, item 42) |
| 43 | `ACIDO_PEPT` | não | Doenças préexistentes (Doença ácido- péptica) (p. 7, item 43) |
| 44 | `AUTO_IMUNE` | não | Doenças préexistentes (Doenças auto- imunes) (p. 7, item 44) |
| 45 | `DT_CHIK_S1` | não | Exame sorológico (IgM) Chikungunya Soro 1 Data da Coleta (p. 8, item 45) |
| 46 | `DT_CHIK_S2` | não | Exame sorológico (IgM) Chikungunya Soro 2 Data da Coleta (p. 8, item 46) |
| 47 | `DT_PRNT` | não | Exame PRNT Data da Coleta (p. 8, item 47) |
| 48 | `RES_CHIKS1` | não | Exame sorológico (IgM) Chikungunya Soro 1 Resultado (p. 8, item 48) |
| 49 | `RES_CHIKS2` | não | Exame sorológico (IgM) Chikungunya Soro 2 Resultado (p. 8, item 49) |
| 50 | `RESUL_PRNT` | não | Exame PRNT Resultado (p. 8, item 50) |
| 51 | `DT_SORO` | sim | Exame sorológico (IgM) Dengue Data da Coleta (p. 8, item 51) |
| 52 | `RESUL_SORO` | sim | Exame sorológico (IgM) Dengue Resultado (p. 8, item 52) |
| 53 | `DT_NS1` | sim | Exame NS1 Data da Coleta (p. 8, item 53) |
| 54 | `RESUL_NS1` | sim | Exame NS1 Resultado (p. 9, item 54) |
| 55 | `DT_VIRAL` | sim | Isolamento Viral Data da Coleta (p. 9, item 55) |
| 56 | `RESUL_VI_N` | sim | Isolamento Viral Resultado (p. 9, item 56) |
| 57 | `DT_PCR` | sim | RT-PCR Data da Coleta (p. 9, item 57) |
| 58 | `RESUL_PCR_` | sim | RT-PCR Resultado (p. 9, item 58) |
| 59 | `SOROTIPO` | sim | Sorotipo (p. 9, item 59) |
| 60 | `HISTOPA_N` | sim | Histopatologia Resultado (p. 9, item 60) |
| 61 | `IMUNOH_N` | sim | Imunohistoquími ca Resultado (p. 9, item 61) |
| 62 | `HOSPITALIZ` | sim | Ocorreu Hospitalização? (p. 9, item 62) |
| 63 | `DT_INTERNA` | sim | Data Da Internação (p. 9, item 63) |
| 64 | `UF` | sim | UF da hospitalização (p. 10, item 64; o PDF traz `COUFINF` neste item) |
| 65 | `MUNICIPIO` | sim | Município (p. 10, item 65) |
| 66 | `TPAUTOCTO` | sim | O caso é autóctone de residência? (p. 10, item 66) |
| 67 | `COUFINF` | sim | UF (provável da fonte de infecção) (p. 11, item 67) |
| 68 | `COPAISINF` | sim | País (provável da fonte de infecção) (p. 12, item 68) |
| 69 | `COMUNINF` | sim | Município (provável da fonte de infecção) (p. 12, item 69) |
| 70 | `CLASSI_FIN` | sim | Classificação final (p. 12, item 70) |
| 71 | `CRITERIO` | sim | Critério confirmação (p. 12, item 71) |
| 72 | `DOENCA_TRA` | sim | Doença relacionada ao (p. 12, item 72) |
| 73 | `CLINC_CHIK` | não | Apresentação clínica Chikungunya (p. 13, item 73) |
| 74 | `EVOLUCAO` | sim | Evolução Do Caso (p. 13, item 74) |
| 75 | `DT_OBITO` | sim | Data do Óbito (p. 13, item 75) |
| 76 | `DT_ENCERRA` | sim | Data Do Encerramento (p. 13, item 76) |
| 77 | `ALRM_HIPOT` | não | Dengue com sinais de alarme (Hipotensão) (p. 13, item 77) |
| 78 | `ALRM_PLAQ` | não | Dengue com sinais de alarme (Queda abrupta de plaquetas) (p. 14, item 78) |
| 79 | `ALRM_VOM` | não | Dengue com sinais de alarme (Vômitos persistentes) (p. 14, item 79) |
| 80 | `ALRM_SANG` | não | Dengue com sinais de alarme (Sangramento de mucosa/outras hemorragias) (p. 14, item 80) |
| 81 | `ALRM_HEMAT` | não | Dengue com sinais de alarme (Aumento hematócrito) (p. 15, item 81) |
| 82 | `ALRM_ABDOM` | não | Dengue com sinais de alarme (Dor abdominal) (p. 15, item 82) |
| 83 | `ALRM_LETAR` | não | Dengue com sinais de alarme (Letargia ou irritabilidade) (p. 15, item 83) |
| 84 | `ALRM_HEPAT` | não | Dengue com sinais de alarme (Hepatomegalia) (p. 16, item 84) |
| 85 | `ALRM_LIQ` | não | Dengue com sinais de alarme (Acúmulo de líquidos) (p. 16, item 85) |
| 86 | `DT_ALRM` | não | Dengue com sinais de alarme Data de início dos sintomas (p. 17, item 86) |
| 87 | `GRAV_PULSO` | não | Dengue grave (Pulso débil ou indectável) (p. 17, item 87) |
| 88 | `GRAV_CONV` | não | Dengue grave (PA convergente) (p. 17, item 88) |
| 89 | `GRAV_ENCH` | não | Dengue grave (Tempo de enchimento capilar) (p. 17, item 89) |
| 90 | `GRAV_INSUF` | não | Dengue grave (Acúmulo de líquidos com insuficiência respiratória) (p. 18, item 90) |
| 91 | `GRAV_TAQUI` | não | Dengue grave (Taquicardia) (p. 18, item 91) |
| 92 | `GRAV_EXTRE` | não | Dengue grave (Extremidade frias) (p. 18, item 92) |
| 93 | `GRAV_HIPOT` | não | Dengue grave (Hipotensão arterial em fase tardia) (p. 18, item 93) |
| 94 | `GRAV_HEMAT` | não | Dengue grave (Hematêmese) (p. 18, item 94) |
| 95 | `GRAV_MELEN` | não | Dengue grave (Melena) (p. 19, item 95) |
| 96 | `GRAV_METRO` | não | Dengue grave (Metrorragia volumosa) (p. 19, item 96) |
| 97 | `GRAV_SANG` | não | Dengue grave (Sangramento do SNC) (p. 19, item 97) |
| 98 | `GRAV_AST` | não | Dengue grave (AST/ALT >1 .000) (p. 19, item 98) |
| 99 | `GRAV_MIOC` | não | Dengue grave (Miocardite ) (p. 19, item 99) |
| 100 | `GRAV_CONSC` | não | Dengue grave (Alteração da consciência) (p. 20, item 100) |
| 101 | `GRAV_ORGAO` | não | Dengue grave (Outros órgãos) (p. 20, item 101) |
| 102 | `DT_GRAV` | não | Dengue grave Data de início dos sintomas (p. 20, item 102) |
| 103 | `MANI_HEMOR` | sim | Manifestações Hemorrágicas (p. 20, item 103) |
| 104 | `EPISTAXE` | sim | Epistaxe (p. 20, item 104) |
| 105 | `GENGIVO` | sim | Gengivorragia (p. 20, item 105) |
| 106 | `METRO` | sim | Metrorragia (p. 20, item 106) |
| 107 | `PETEQUIAS` | sim | Petéquias (p. 20, item 107) |
| 108 | `HEMATURA` | sim | Hematúria (p. 21, item 108) |
| 109 | `SANGRAM` | sim | Sangramaneto gastrointestinal (p. 21, item 109) |
| 110 | `LACO_N` | sim | Prova do laço positiva (p. 21, item 110) |
| 111 | `PLASMATICO` | sim | Extravasamento plasmático (p. 21, item 111) |
| 112 | `EVIDENCIA` | sim | Evidenciado (p. 21, item 112) |
| 113 | `PLAQ_MENOR` | sim | Plaquetas (p. 21, item 113) |
| 114 | `CON_FHD` | sim | Caso de FHD (p. 21, item 114) |
| 115 | `COMPLICA` | sim | Caso de dengue com complicações (p. 21, item 115) |
| 116 | `TP_SISTEMA` | sim | Tipo de Sistema (p. 21, item 116) |
| 117 | `NDUPLIC_N` | sim | Não Listar/ Não Contar (p. 21, item 117) |
| 118 | `DT_DIGITA` | sim | Data da digitação (p. 21, item 118) |
| 119 | `CS_FLXRET` | sim | Fluxo de retorno (p. 22, item 119) |
| 120 | `FLXRECEBI` | sim | Recebida por fluxo de retorno (campo interno) (p. 22, item 120) |
| 121 | `MIGRADO_W` | sim | Identifica migração (campo interno) (p. 22, item 121) |

## Observações do cruzamento

- 66 colunas de 2013 aparecem em 2014; 55 colunas foram acrescentadas.
- O PDF escreve `CLINIC_CHIK`, enquanto o CSV escreve `CLINC_CHIK`.
- O PDF repete `COUFINF` nos itens 64 e 67; o CSV contém esse campo uma vez.
- No item 64, a descrição do PDF é a UF da hospitalização, mas o código impresso é `COUFINF`, repetido no item 67. O CSV usa `UF` para hospitalização e `COUFINF` para provável fonte de infecção.
- Valores como `23.0` no CSV de amostra do repositório são representações numéricas; a comparação de códigos deve tratá-los como texto normalizado.
