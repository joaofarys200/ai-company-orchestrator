# ProjectBuilder Flight Recorder Timeline

| Ordem | Fase | Evento | Inicio | Duracao ms | Estado | Progresso |
|---:|---|---|---:|---:|---|---:|
| 1 | EXECUTION | mission_execution_started | 0.0 |  | OBSERVED |  |
| 2 | EXECUTION | project_builder_dispatch_started | 0.0 |  | OBSERVED |  |
| 3 | EXECUTION | build_project_entered | 16.0 |  | OBSERVED |  |
| 4 | PLANNING | span_started | 16.0 |  | RUNNING |  |
| 5 | PREPARATION | prompt_build_started | 16.0 |  | OBSERVED |  |
| 6 | PREPARATION | prompt_build_completed | 16.0 |  | OBSERVED |  |
| 7 | PREPARATION | request_payload_built | 16.0 |  | OBSERVED |  |
| 8 | REQUESTER | requester_started | 16.0 |  | OBSERVED |  |
| 9 | JOURNAL | journal_write_started | 16.0 |  | OBSERVED |  |
| 10 | JOURNAL | journal_write_completed | 16.0 |  | COMPLETED |  |
| 11 | REQUESTER | readiness_check_started | 31.0 |  | OBSERVED |  |
| 12 | JOURNAL | journal_write_started | 31.0 |  | OBSERVED |  |
| 13 | JOURNAL | journal_write_completed | 31.0 |  | COMPLETED |  |
| 14 | JOURNAL | journal_write_started | 203.0 |  | OBSERVED |  |
| 15 | JOURNAL | journal_write_completed | 219.0 |  | COMPLETED |  |
| 16 | REQUESTER | readiness_check_completed | 219.0 |  | COMPLETED |  |
| 17 | REQUESTER | model_attempt_started | 219.0 |  | OBSERVED |  |
| 18 | REQUESTER | http_request_started | 359.0 |  | OBSERVED |  |
| 19 | PLANNING | heartbeat | 5016.0 |  | RUNNING |  |
| 20 | PLANNING | heartbeat | 10016.0 |  | RUNNING |  |
| 21 | REQUESTER | response_headers_received | 12422.0 |  | COMPLETED |  |
| 22 | JOURNAL | journal_write_started | 12422.0 |  | OBSERVED |  |
| 23 | JOURNAL | journal_write_completed | 12438.0 |  | COMPLETED |  |
| 24 | REQUESTER | first_response_byte | 12438.0 |  | OBSERVED |  |
| 25 | REQUESTER | first_http_chunk | 12438.0 |  | OBSERVED |  |
| 26 | REQUESTER | first_nonempty_content | 12438.0 |  | OBSERVED |  |
| 27 | REQUESTER | stream_progress | 12438.0 |  | OBSERVED | 1 |
| 28 | REQUESTER | stream_progress | 12563.0 |  | OBSERVED | 2 |
| 29 | REQUESTER | stream_progress | 12594.0 |  | OBSERVED | 3 |
| 30 | REQUESTER | stream_progress | 12641.0 |  | OBSERVED | 4 |
| 31 | REQUESTER | stream_progress | 12672.0 |  | OBSERVED | 5 |
| 32 | REQUESTER | stream_progress | 12719.0 |  | OBSERVED | 6 |
| 33 | REQUESTER | stream_progress | 12750.0 |  | OBSERVED | 7 |
| 34 | REQUESTER | stream_progress | 12797.0 |  | OBSERVED | 8 |
| 35 | REQUESTER | stream_progress | 12844.0 |  | OBSERVED | 9 |
| 36 | REQUESTER | stream_progress | 12875.0 |  | OBSERVED | 10 |
| 37 | REQUESTER | stream_progress | 12922.0 |  | OBSERVED | 11 |
| 38 | REQUESTER | stream_progress | 12953.0 |  | OBSERVED | 12 |
| 39 | REQUESTER | stream_progress | 13078.0 |  | OBSERVED | 13 |
| 40 | REQUESTER | stream_progress | 13109.0 |  | OBSERVED | 14 |
| 41 | REQUESTER | stream_progress | 13156.0 |  | OBSERVED | 15 |
| 42 | REQUESTER | stream_progress | 13203.0 |  | OBSERVED | 16 |
| 43 | REQUESTER | stream_progress | 13234.0 |  | OBSERVED | 17 |
| 44 | REQUESTER | stream_progress | 13281.0 |  | OBSERVED | 18 |
| 45 | REQUESTER | stream_progress | 13313.0 |  | OBSERVED | 19 |
| 46 | REQUESTER | stream_progress | 13359.0 |  | OBSERVED | 20 |
| 47 | REQUESTER | stream_progress | 13391.0 |  | OBSERVED | 21 |
| 48 | REQUESTER | stream_progress | 13516.0 |  | OBSERVED | 22 |
| 49 | REQUESTER | stream_progress | 13563.0 |  | OBSERVED | 23 |
| 50 | REQUESTER | stream_progress | 13594.0 |  | OBSERVED | 24 |
| 51 | REQUESTER | stream_progress | 13641.0 |  | OBSERVED | 25 |
| 52 | REQUESTER | stream_progress | 13750.0 |  | OBSERVED | 26 |
| 53 | REQUESTER | stream_progress | 13797.0 |  | OBSERVED | 27 |
| 54 | REQUESTER | stream_progress | 13828.0 |  | OBSERVED | 28 |
| 55 | REQUESTER | stream_progress | 13938.0 |  | OBSERVED | 29 |
| 56 | REQUESTER | stream_progress | 13984.0 |  | OBSERVED | 30 |
| 57 | REQUESTER | stream_progress | 14016.0 |  | OBSERVED | 31 |
| 58 | REQUESTER | stream_progress | 14125.0 |  | OBSERVED | 32 |
| 59 | REQUESTER | stream_progress | 14156.0 |  | OBSERVED | 33 |
| 60 | REQUESTER | stream_progress | 14188.0 |  | OBSERVED | 34 |
| 61 | REQUESTER | stream_progress | 14234.0 |  | OBSERVED | 35 |
| 62 | REQUESTER | stream_progress | 14344.0 |  | OBSERVED | 36 |
| 63 | REQUESTER | stream_progress | 14375.0 |  | OBSERVED | 37 |
| 64 | REQUESTER | stream_progress | 14406.0 |  | OBSERVED | 38 |
| 65 | JOURNAL | journal_write_started | 14516.0 |  | OBSERVED |  |
| 66 | JOURNAL | journal_write_completed | 14531.0 |  | COMPLETED |  |
| 67 | REQUESTER | stream_progress | 14531.0 |  | OBSERVED | 39 |
| 68 | REQUESTER | stream_progress | 14641.0 |  | OBSERVED | 40 |
| 69 | REQUESTER | stream_progress | 14672.0 |  | OBSERVED | 41 |
| 70 | REQUESTER | stream_progress | 14719.0 |  | OBSERVED | 42 |
| 71 | REQUESTER | stream_progress | 14750.0 |  | OBSERVED | 43 |
| 72 | REQUESTER | stream_progress | 14859.0 |  | OBSERVED | 44 |
| 73 | REQUESTER | stream_progress | 14984.0 |  | OBSERVED | 45 |
| 74 | REQUESTER | stream_progress | 15016.0 |  | OBSERVED | 46 |
| 75 | PLANNING | heartbeat | 15047.0 |  | RUNNING | 46 |
| 76 | REQUESTER | stream_progress | 15063.0 |  | OBSERVED | 47 |
| 77 | REQUESTER | stream_progress | 15094.0 |  | OBSERVED | 48 |
| 78 | REQUESTER | stream_progress | 15141.0 |  | OBSERVED | 49 |
| 79 | REQUESTER | stream_progress | 15172.0 |  | OBSERVED | 50 |
| 80 | REQUESTER | stream_progress | 15203.0 |  | OBSERVED | 51 |
| 81 | REQUESTER | stream_progress | 15328.0 |  | OBSERVED | 52 |
| 82 | REQUESTER | stream_progress | 15359.0 |  | OBSERVED | 53 |
| 83 | REQUESTER | stream_progress | 15406.0 |  | OBSERVED | 54 |
| 84 | REQUESTER | stream_progress | 15438.0 |  | OBSERVED | 55 |
| 85 | REQUESTER | stream_progress | 15469.0 |  | OBSERVED | 56 |
| 86 | REQUESTER | stream_progress | 15516.0 |  | OBSERVED | 57 |
| 87 | REQUESTER | stream_progress | 15594.0 |  | OBSERVED | 58 |
| 88 | REQUESTER | stream_progress | 15625.0 |  | OBSERVED | 59 |
| 89 | REQUESTER | stream_progress | 15672.0 |  | OBSERVED | 60 |
| 90 | REQUESTER | stream_progress | 15703.0 |  | OBSERVED | 61 |
| 91 | REQUESTER | stream_progress | 15750.0 |  | OBSERVED | 62 |
| 92 | REQUESTER | stream_progress | 15781.0 |  | OBSERVED | 63 |
| 93 | REQUESTER | stream_progress | 15828.0 |  | OBSERVED | 64 |
| 94 | REQUESTER | stream_progress | 15859.0 |  | OBSERVED | 65 |
| 95 | REQUESTER | stream_progress | 15891.0 |  | OBSERVED | 66 |
| 96 | REQUESTER | stream_progress | 15938.0 |  | OBSERVED | 67 |
| 97 | REQUESTER | stream_progress | 15969.0 |  | OBSERVED | 68 |
| 98 | REQUESTER | stream_progress | 16047.0 |  | OBSERVED | 69 |
| 99 | REQUESTER | stream_progress | 16094.0 |  | OBSERVED | 70 |
| 100 | REQUESTER | stream_progress | 16141.0 |  | OBSERVED | 71 |
| 101 | REQUESTER | stream_progress | 16172.0 |  | OBSERVED | 72 |
| 102 | REQUESTER | stream_progress | 16219.0 |  | OBSERVED | 73 |
| 103 | REQUESTER | stream_progress | 16250.0 |  | OBSERVED | 74 |
| 104 | REQUESTER | stream_progress | 16297.0 |  | OBSERVED | 75 |
| 105 | REQUESTER | stream_progress | 16344.0 |  | OBSERVED | 76 |
| 106 | REQUESTER | stream_progress | 16375.0 |  | OBSERVED | 77 |
| 107 | REQUESTER | stream_progress | 16422.0 |  | OBSERVED | 78 |
| 108 | REQUESTER | stream_progress | 16453.0 |  | OBSERVED | 79 |
| 109 | JOURNAL | journal_write_started | 16531.0 |  | OBSERVED |  |
| 110 | JOURNAL | journal_write_completed | 16547.0 |  | COMPLETED |  |
| 111 | REQUESTER | stream_progress | 16547.0 |  | OBSERVED | 80 |
| 112 | REQUESTER | stream_progress | 16578.0 |  | OBSERVED | 81 |
| 113 | REQUESTER | stream_progress | 16625.0 |  | OBSERVED | 82 |
| 114 | REQUESTER | stream_progress | 16656.0 |  | OBSERVED | 83 |
| 115 | REQUESTER | stream_progress | 16703.0 |  | OBSERVED | 84 |
| 116 | REQUESTER | stream_progress | 16734.0 |  | OBSERVED | 85 |
| 117 | REQUESTER | stream_progress | 16781.0 |  | OBSERVED | 86 |
| 118 | REQUESTER | stream_progress | 16813.0 |  | OBSERVED | 87 |
| 119 | REQUESTER | stream_progress | 16938.0 |  | OBSERVED | 88 |
| 120 | REQUESTER | stream_progress | 17063.0 |  | OBSERVED | 89 |
| 121 | REQUESTER | stream_progress | 17172.0 |  | OBSERVED | 90 |
| 122 | REQUESTER | stream_progress | 17219.0 |  | OBSERVED | 91 |
| 123 | REQUESTER | stream_progress | 17266.0 |  | OBSERVED | 92 |
| 124 | REQUESTER | stream_progress | 17297.0 |  | OBSERVED | 93 |
| 125 | REQUESTER | stream_progress | 17344.0 |  | OBSERVED | 94 |
| 126 | REQUESTER | stream_progress | 17375.0 |  | OBSERVED | 95 |
| 127 | REQUESTER | stream_progress | 17422.0 |  | OBSERVED | 96 |
| 128 | REQUESTER | stream_progress | 17547.0 |  | OBSERVED | 97 |
| 129 | REQUESTER | stream_progress | 17578.0 |  | OBSERVED | 98 |
| 130 | REQUESTER | stream_progress | 17625.0 |  | OBSERVED | 99 |
| 131 | REQUESTER | stream_progress | 17656.0 |  | OBSERVED | 100 |
| 132 | REQUESTER | stream_progress | 17703.0 |  | OBSERVED | 101 |
| 133 | REQUESTER | stream_progress | 17734.0 |  | OBSERVED | 102 |
| 134 | REQUESTER | stream_progress | 17781.0 |  | OBSERVED | 103 |
| 135 | REQUESTER | stream_progress | 17828.0 |  | OBSERVED | 104 |
| 136 | REQUESTER | stream_progress | 17859.0 |  | OBSERVED | 105 |
| 137 | REQUESTER | stream_progress | 17906.0 |  | OBSERVED | 106 |
| 138 | REQUESTER | stream_progress | 17938.0 |  | OBSERVED | 107 |
| 139 | REQUESTER | stream_progress | 17984.0 |  | OBSERVED | 108 |
| 140 | REQUESTER | stream_progress | 18016.0 |  | OBSERVED | 109 |
| 141 | REQUESTER | stream_progress | 18063.0 |  | OBSERVED | 110 |
| 142 | REQUESTER | stream_progress | 18094.0 |  | OBSERVED | 111 |
| 143 | REQUESTER | stream_progress | 18141.0 |  | OBSERVED | 112 |
| 144 | REQUESTER | stream_progress | 18172.0 |  | OBSERVED | 113 |
| 145 | REQUESTER | stream_progress | 18219.0 |  | OBSERVED | 114 |
| 146 | REQUESTER | stream_progress | 18250.0 |  | OBSERVED | 115 |
| 147 | REQUESTER | stream_progress | 18297.0 |  | OBSERVED | 116 |
| 148 | REQUESTER | stream_progress | 18344.0 |  | OBSERVED | 117 |
| 149 | REQUESTER | stream_progress | 18375.0 |  | OBSERVED | 118 |
| 150 | REQUESTER | stream_progress | 18422.0 |  | OBSERVED | 119 |
| 151 | REQUESTER | stream_progress | 18453.0 |  | OBSERVED | 120 |
| 152 | REQUESTER | stream_progress | 18500.0 |  | OBSERVED | 121 |
| 153 | JOURNAL | journal_write_started | 18547.0 |  | OBSERVED |  |
| 154 | JOURNAL | journal_write_completed | 18547.0 |  | COMPLETED |  |
| 155 | REQUESTER | stream_progress | 18563.0 |  | OBSERVED | 122 |
| 156 | REQUESTER | stream_progress | 18625.0 |  | OBSERVED | 123 |
| 157 | REQUESTER | stream_progress | 18656.0 |  | OBSERVED | 124 |
| 158 | REQUESTER | stream_progress | 18703.0 |  | OBSERVED | 125 |
| 159 | REQUESTER | stream_progress | 18734.0 |  | OBSERVED | 126 |
| 160 | REQUESTER | stream_progress | 18781.0 |  | OBSERVED | 127 |
| 161 | REQUESTER | stream_progress | 18813.0 |  | OBSERVED | 128 |
| 162 | REQUESTER | stream_progress | 18859.0 |  | OBSERVED | 129 |
| 163 | REQUESTER | stream_progress | 18906.0 |  | OBSERVED | 130 |
| 164 | REQUESTER | stream_progress | 18953.0 |  | OBSERVED | 131 |
| 165 | REQUESTER | stream_progress | 19000.0 |  | OBSERVED | 132 |
| 166 | REQUESTER | stream_progress | 19078.0 |  | OBSERVED | 133 |
| 167 | REQUESTER | stream_progress | 19109.0 |  | OBSERVED | 134 |
| 168 | REQUESTER | stream_progress | 19156.0 |  | OBSERVED | 135 |
| 169 | REQUESTER | stream_progress | 19203.0 |  | OBSERVED | 136 |
| 170 | REQUESTER | stream_progress | 19234.0 |  | OBSERVED | 137 |
| 171 | REQUESTER | stream_progress | 19281.0 |  | OBSERVED | 138 |
| 172 | REQUESTER | stream_progress | 19328.0 |  | OBSERVED | 139 |
| 173 | REQUESTER | stream_progress | 19359.0 |  | OBSERVED | 140 |
| 174 | REQUESTER | stream_progress | 19438.0 |  | OBSERVED | 141 |
| 175 | REQUESTER | stream_progress | 19484.0 |  | OBSERVED | 142 |
| 176 | REQUESTER | stream_progress | 19516.0 |  | OBSERVED | 143 |
| 177 | REQUESTER | stream_progress | 19563.0 |  | OBSERVED | 144 |
| 178 | REQUESTER | stream_progress | 19594.0 |  | OBSERVED | 145 |
| 179 | REQUESTER | stream_progress | 19641.0 |  | OBSERVED | 146 |
| 180 | REQUESTER | stream_progress | 19672.0 |  | OBSERVED | 147 |
| 181 | REQUESTER | stream_progress | 19750.0 |  | OBSERVED | 148 |
| 182 | REQUESTER | stream_progress | 19797.0 |  | OBSERVED | 149 |
| 183 | REQUESTER | stream_progress | 19844.0 |  | OBSERVED | 150 |
| 184 | REQUESTER | stream_progress | 19875.0 |  | OBSERVED | 151 |
| 185 | REQUESTER | stream_progress | 19969.0 |  | OBSERVED | 152 |
| 186 | REQUESTER | stream_progress | 20000.0 |  | OBSERVED | 153 |
| 187 | REQUESTER | stream_progress | 20047.0 |  | OBSERVED | 154 |
| 188 | PLANNING | heartbeat | 20047.0 |  | RUNNING | 154 |
| 189 | REQUESTER | stream_progress | 20078.0 |  | OBSERVED | 155 |
| 190 | REQUESTER | stream_progress | 20125.0 |  | OBSERVED | 156 |
| 191 | REQUESTER | stream_progress | 20156.0 |  | OBSERVED | 157 |
| 192 | REQUESTER | stream_progress | 20203.0 |  | OBSERVED | 158 |
| 193 | REQUESTER | stream_progress | 20250.0 |  | OBSERVED | 159 |
| 194 | REQUESTER | stream_progress | 20328.0 |  | OBSERVED | 160 |
| 195 | REQUESTER | stream_progress | 20359.0 |  | OBSERVED | 161 |
| 196 | REQUESTER | stream_progress | 20406.0 |  | OBSERVED | 162 |
| 197 | REQUESTER | stream_progress | 20438.0 |  | OBSERVED | 163 |
| 198 | REQUESTER | stream_progress | 20484.0 |  | OBSERVED | 164 |
| 199 | JOURNAL | journal_write_started | 20563.0 |  | OBSERVED |  |
| 200 | JOURNAL | journal_write_completed | 20578.0 |  | COMPLETED |  |
| 201 | REQUESTER | stream_progress | 20578.0 |  | OBSERVED | 165 |
| 202 | REQUESTER | stream_progress | 20609.0 |  | OBSERVED | 166 |
| 203 | REQUESTER | stream_progress | 20641.0 |  | OBSERVED | 167 |
| 204 | REQUESTER | stream_progress | 20688.0 |  | OBSERVED | 168 |
| 205 | REQUESTER | stream_progress | 20719.0 |  | OBSERVED | 169 |
| 206 | REQUESTER | stream_progress | 20766.0 |  | OBSERVED | 170 |
| 207 | REQUESTER | stream_progress | 20813.0 |  | OBSERVED | 171 |
| 208 | REQUESTER | stream_progress | 20844.0 |  | OBSERVED | 172 |
| 209 | REQUESTER | stream_progress | 20891.0 |  | OBSERVED | 173 |
| 210 | REQUESTER | stream_progress | 20938.0 |  | OBSERVED | 174 |
| 211 | REQUESTER | stream_progress | 20969.0 |  | OBSERVED | 175 |
| 212 | REQUESTER | stream_progress | 21016.0 |  | OBSERVED | 176 |
| 213 | REQUESTER | stream_progress | 21047.0 |  | OBSERVED | 177 |
| 214 | REQUESTER | stream_progress | 21125.0 |  | OBSERVED | 178 |
| 215 | REQUESTER | stream_progress | 21172.0 |  | OBSERVED | 179 |
| 216 | REQUESTER | stream_progress | 21203.0 |  | OBSERVED | 180 |
| 217 | REQUESTER | stream_progress | 21250.0 |  | OBSERVED | 181 |
| 218 | REQUESTER | stream_progress | 21297.0 |  | OBSERVED | 182 |
| 219 | REQUESTER | stream_progress | 21328.0 |  | OBSERVED | 183 |
| 220 | REQUESTER | stream_progress | 21375.0 |  | OBSERVED | 184 |
| 221 | REQUESTER | stream_progress | 21406.0 |  | OBSERVED | 185 |
| 222 | REQUESTER | stream_progress | 21453.0 |  | OBSERVED | 186 |
| 223 | REQUESTER | stream_progress | 21484.0 |  | OBSERVED | 187 |
| 224 | REQUESTER | stream_progress | 21531.0 |  | OBSERVED | 188 |
| 225 | REQUESTER | stream_progress | 21578.0 |  | OBSERVED | 189 |
| 226 | REQUESTER | stream_progress | 21609.0 |  | OBSERVED | 190 |
| 227 | REQUESTER | stream_progress | 21656.0 |  | OBSERVED | 191 |
| 228 | REQUESTER | stream_progress | 21688.0 |  | OBSERVED | 192 |
| 229 | REQUESTER | stream_progress | 21734.0 |  | OBSERVED | 193 |
| 230 | REQUESTER | stream_progress | 21781.0 |  | OBSERVED | 194 |
| 231 | REQUESTER | stream_progress | 21813.0 |  | OBSERVED | 195 |
| 232 | REQUESTER | stream_progress | 21859.0 |  | OBSERVED | 196 |
| 233 | REQUESTER | stream_progress | 21906.0 |  | OBSERVED | 197 |
| 234 | REQUESTER | stream_progress | 21938.0 |  | OBSERVED | 198 |
| 235 | REQUESTER | stream_progress | 21984.0 |  | OBSERVED | 199 |
| 236 | REQUESTER | stream_progress | 22016.0 |  | OBSERVED | 200 |
| 237 | REQUESTER | stream_progress | 22063.0 |  | OBSERVED | 201 |
| 238 | REQUESTER | stream_progress | 22172.0 |  | OBSERVED | 202 |
| 239 | REQUESTER | stream_progress | 22313.0 |  | OBSERVED | 203 |
| 240 | REQUESTER | stream_progress | 22422.0 |  | OBSERVED | 204 |
| 241 | REQUESTER | stream_progress | 22469.0 |  | OBSERVED | 205 |
| 242 | REQUESTER | stream_progress | 22500.0 |  | OBSERVED | 206 |
| 243 | REQUESTER | stream_progress | 22547.0 |  | OBSERVED | 207 |
| 244 | JOURNAL | journal_write_started | 22578.0 |  | OBSERVED |  |
| 245 | JOURNAL | journal_write_completed | 22594.0 |  | COMPLETED |  |
| 246 | REQUESTER | stream_progress | 22594.0 |  | OBSERVED | 208 |
| 247 | REQUESTER | stream_progress | 22625.0 |  | OBSERVED | 209 |
| 248 | REQUESTER | stream_progress | 22672.0 |  | OBSERVED | 210 |
| 249 | REQUESTER | stream_progress | 22781.0 |  | OBSERVED | 211 |
| 250 | REQUESTER | stream_progress | 22828.0 |  | OBSERVED | 212 |
| 251 | REQUESTER | stream_progress | 22859.0 |  | OBSERVED | 213 |
| 252 | REQUESTER | stream_progress | 22906.0 |  | OBSERVED | 214 |
| 253 | REQUESTER | stream_progress | 22938.0 |  | OBSERVED | 215 |
| 254 | REQUESTER | stream_progress | 22984.0 |  | OBSERVED | 216 |
| 255 | REQUESTER | stream_progress | 23031.0 |  | OBSERVED | 217 |
| 256 | REQUESTER | stream_progress | 23063.0 |  | OBSERVED | 218 |
| 257 | REQUESTER | stream_progress | 23109.0 |  | OBSERVED | 219 |
| 258 | REQUESTER | stream_progress | 23141.0 |  | OBSERVED | 220 |
| 259 | REQUESTER | stream_progress | 23188.0 |  | OBSERVED | 221 |
| 260 | REQUESTER | stream_progress | 23219.0 |  | OBSERVED | 222 |
| 261 | REQUESTER | stream_progress | 23266.0 |  | OBSERVED | 223 |
| 262 | REQUESTER | stream_progress | 23313.0 |  | OBSERVED | 224 |
| 263 | REQUESTER | stream_progress | 23344.0 |  | OBSERVED | 225 |
| 264 | REQUESTER | stream_progress | 23391.0 |  | OBSERVED | 226 |
| 265 | REQUESTER | stream_progress | 23422.0 |  | OBSERVED | 227 |
| 266 | REQUESTER | stream_progress | 23469.0 |  | OBSERVED | 228 |
| 267 | REQUESTER | stream_progress | 23500.0 |  | OBSERVED | 229 |
| 268 | REQUESTER | stream_progress | 23547.0 |  | OBSERVED | 230 |
| 269 | REQUESTER | stream_progress | 23578.0 |  | OBSERVED | 231 |
| 270 | REQUESTER | stream_progress | 23625.0 |  | OBSERVED | 232 |
| 271 | REQUESTER | stream_progress | 23672.0 |  | OBSERVED | 233 |
| 272 | REQUESTER | stream_progress | 23703.0 |  | OBSERVED | 234 |
| 273 | REQUESTER | stream_progress | 23750.0 |  | OBSERVED | 235 |
| 274 | REQUESTER | stream_progress | 23781.0 |  | OBSERVED | 236 |
| 275 | REQUESTER | stream_progress | 23828.0 |  | OBSERVED | 237 |
| 276 | REQUESTER | stream_progress | 23859.0 |  | OBSERVED | 238 |
| 277 | REQUESTER | stream_progress | 23906.0 |  | OBSERVED | 239 |
| 278 | REQUESTER | stream_progress | 23938.0 |  | OBSERVED | 240 |
| 279 | REQUESTER | stream_progress | 23984.0 |  | OBSERVED | 241 |
| 280 | REQUESTER | stream_progress | 24031.0 |  | OBSERVED | 242 |
| 281 | REQUESTER | stream_progress | 24063.0 |  | OBSERVED | 243 |
| 282 | REQUESTER | stream_progress | 24109.0 |  | OBSERVED | 244 |
| 283 | REQUESTER | stream_progress | 24141.0 |  | OBSERVED | 245 |
| 284 | REQUESTER | stream_progress | 24188.0 |  | OBSERVED | 246 |
| 285 | REQUESTER | stream_progress | 24219.0 |  | OBSERVED | 247 |
| 286 | REQUESTER | stream_progress | 24266.0 |  | OBSERVED | 248 |
| 287 | REQUESTER | stream_progress | 24297.0 |  | OBSERVED | 249 |
| 288 | REQUESTER | stream_progress | 24344.0 |  | OBSERVED | 250 |
| 289 | REQUESTER | stream_progress | 24391.0 |  | OBSERVED | 251 |
| 290 | REQUESTER | stream_progress | 24422.0 |  | OBSERVED | 252 |
| 291 | REQUESTER | stream_progress | 24469.0 |  | OBSERVED | 253 |
| 292 | REQUESTER | stream_progress | 24500.0 |  | OBSERVED | 254 |
| 293 | REQUESTER | stream_progress | 24547.0 |  | OBSERVED | 255 |
| 294 | JOURNAL | journal_write_started | 24578.0 |  | OBSERVED |  |
| 295 | JOURNAL | journal_write_completed | 24594.0 |  | COMPLETED |  |
| 296 | REQUESTER | stream_progress | 24594.0 |  | OBSERVED | 256 |
| 297 | REQUESTER | stream_progress | 24625.0 |  | OBSERVED | 257 |
| 298 | REQUESTER | stream_progress | 24656.0 |  | OBSERVED | 258 |
| 299 | REQUESTER | stream_progress | 24703.0 |  | OBSERVED | 259 |
| 300 | REQUESTER | stream_progress | 24734.0 |  | OBSERVED | 260 |
| 301 | REQUESTER | stream_progress | 24781.0 |  | OBSERVED | 261 |
| 302 | REQUESTER | stream_progress | 24906.0 |  | OBSERVED | 262 |
| 303 | REQUESTER | stream_progress | 25016.0 |  | OBSERVED | 263 |
| 304 | PLANNING | heartbeat | 25063.0 |  | RUNNING | 263 |
| 305 | REQUESTER | stream_progress | 25141.0 |  | OBSERVED | 264 |
| 306 | REQUESTER | stream_progress | 25188.0 |  | OBSERVED | 265 |
| 307 | REQUESTER | stream_progress | 25219.0 |  | OBSERVED | 266 |
| 308 | REQUESTER | stream_progress | 25266.0 |  | OBSERVED | 267 |
| 309 | REQUESTER | stream_progress | 25297.0 |  | OBSERVED | 268 |
| 310 | REQUESTER | stream_progress | 25344.0 |  | OBSERVED | 269 |
| 311 | REQUESTER | stream_progress | 25375.0 |  | OBSERVED | 270 |
| 312 | REQUESTER | stream_progress | 25500.0 |  | OBSERVED | 271 |
| 313 | REQUESTER | stream_progress | 25547.0 |  | OBSERVED | 272 |
| 314 | REQUESTER | stream_progress | 25578.0 |  | OBSERVED | 273 |
| 315 | REQUESTER | stream_progress | 25625.0 |  | OBSERVED | 274 |
| 316 | REQUESTER | stream_progress | 25656.0 |  | OBSERVED | 275 |
| 317 | REQUESTER | stream_progress | 25703.0 |  | OBSERVED | 276 |
| 318 | REQUESTER | stream_progress | 25734.0 |  | OBSERVED | 277 |
| 319 | REQUESTER | stream_progress | 25781.0 |  | OBSERVED | 278 |
| 320 | REQUESTER | stream_progress | 25813.0 |  | OBSERVED | 279 |
| 321 | REQUESTER | stream_progress | 25859.0 |  | OBSERVED | 280 |
| 322 | REQUESTER | stream_progress | 25891.0 |  | OBSERVED | 281 |
| 323 | REQUESTER | stream_progress | 25938.0 |  | OBSERVED | 282 |
| 324 | REQUESTER | stream_progress | 25984.0 |  | OBSERVED | 283 |
| 325 | REQUESTER | stream_progress | 26016.0 |  | OBSERVED | 284 |
| 326 | REQUESTER | stream_progress | 26063.0 |  | OBSERVED | 285 |
| 327 | REQUESTER | stream_progress | 26094.0 |  | OBSERVED | 286 |
| 328 | REQUESTER | stream_progress | 26141.0 |  | OBSERVED | 287 |
| 329 | REQUESTER | stream_progress | 26172.0 |  | OBSERVED | 288 |
| 330 | REQUESTER | stream_progress | 26219.0 |  | OBSERVED | 289 |
| 331 | REQUESTER | stream_progress | 26250.0 |  | OBSERVED | 290 |
| 332 | REQUESTER | stream_progress | 26297.0 |  | OBSERVED | 291 |
| 333 | REQUESTER | stream_progress | 26344.0 |  | OBSERVED | 292 |
| 334 | REQUESTER | stream_progress | 26375.0 |  | OBSERVED | 293 |
| 335 | REQUESTER | stream_progress | 26422.0 |  | OBSERVED | 294 |
| 336 | REQUESTER | stream_progress | 26453.0 |  | OBSERVED | 295 |
| 337 | REQUESTER | stream_progress | 26500.0 |  | OBSERVED | 296 |
| 338 | REQUESTER | stream_progress | 26547.0 |  | OBSERVED | 297 |
| 339 | JOURNAL | journal_write_started | 26578.0 |  | OBSERVED |  |
| 340 | JOURNAL | journal_write_completed | 26594.0 |  | COMPLETED |  |
| 341 | REQUESTER | stream_progress | 26594.0 |  | OBSERVED | 298 |
| 342 | REQUESTER | stream_progress | 26625.0 |  | OBSERVED | 299 |
| 343 | REQUESTER | stream_progress | 26656.0 |  | OBSERVED | 300 |
| 344 | REQUESTER | stream_progress | 26703.0 |  | OBSERVED | 301 |
| 345 | REQUESTER | stream_progress | 26734.0 |  | OBSERVED | 302 |
| 346 | REQUESTER | stream_progress | 26828.0 |  | OBSERVED | 303 |
| 347 | REQUESTER | stream_progress | 26859.0 |  | OBSERVED | 304 |
| 348 | REQUESTER | stream_progress | 26906.0 |  | OBSERVED | 305 |
| 349 | REQUESTER | stream_progress | 26938.0 |  | OBSERVED | 306 |
| 350 | REQUESTER | stream_progress | 26984.0 |  | OBSERVED | 307 |
| 351 | REQUESTER | stream_progress | 27016.0 |  | OBSERVED | 308 |
| 352 | REQUESTER | stream_progress | 27063.0 |  | OBSERVED | 309 |
| 353 | REQUESTER | stream_progress | 27094.0 |  | OBSERVED | 310 |
| 354 | REQUESTER | stream_progress | 27141.0 |  | OBSERVED | 311 |
| 355 | REQUESTER | stream_progress | 27188.0 |  | OBSERVED | 312 |
| 356 | REQUESTER | stream_progress | 27219.0 |  | OBSERVED | 313 |
| 357 | REQUESTER | stream_progress | 27266.0 |  | OBSERVED | 314 |
| 358 | REQUESTER | stream_progress | 27297.0 |  | OBSERVED | 315 |
| 359 | REQUESTER | stream_progress | 27375.0 |  | OBSERVED | 316 |
| 360 | REQUESTER | stream_progress | 27422.0 |  | OBSERVED | 317 |
| 361 | REQUESTER | stream_progress | 27469.0 |  | OBSERVED | 318 |
| 362 | REQUESTER | stream_progress | 27500.0 |  | OBSERVED | 319 |
| 363 | REQUESTER | stream_progress | 27547.0 |  | OBSERVED | 320 |
| 364 | REQUESTER | stream_progress | 27578.0 |  | OBSERVED | 321 |
| 365 | REQUESTER | stream_progress | 27625.0 |  | OBSERVED | 322 |
| 366 | REQUESTER | stream_progress | 27656.0 |  | OBSERVED | 323 |
| 367 | REQUESTER | stream_progress | 27703.0 |  | OBSERVED | 324 |
| 368 | REQUESTER | stream_progress | 27734.0 |  | OBSERVED | 325 |
| 369 | REQUESTER | stream_progress | 27781.0 |  | OBSERVED | 326 |
| 370 | REQUESTER | stream_progress | 27813.0 |  | OBSERVED | 327 |
| 371 | REQUESTER | stream_progress | 27859.0 |  | OBSERVED | 328 |
| 372 | REQUESTER | stream_progress | 27906.0 |  | OBSERVED | 329 |
| 373 | REQUESTER | stream_progress | 27938.0 |  | OBSERVED | 330 |
| 374 | REQUESTER | stream_progress | 27984.0 |  | OBSERVED | 331 |
| 375 | REQUESTER | stream_progress | 28016.0 |  | OBSERVED | 332 |
| 376 | REQUESTER | stream_progress | 28063.0 |  | OBSERVED | 333 |
| 377 | REQUESTER | stream_progress | 28094.0 |  | OBSERVED | 334 |
| 378 | REQUESTER | stream_progress | 28188.0 |  | OBSERVED | 335 |
| 379 | REQUESTER | stream_progress | 28219.0 |  | OBSERVED | 336 |
| 380 | REQUESTER | stream_progress | 28266.0 |  | OBSERVED | 337 |
| 381 | REQUESTER | stream_progress | 28297.0 |  | OBSERVED | 338 |
| 382 | REQUESTER | stream_progress | 28344.0 |  | OBSERVED | 339 |
| 383 | REQUESTER | stream_progress | 28422.0 |  | OBSERVED | 340 |
| 384 | REQUESTER | stream_progress | 28453.0 |  | OBSERVED | 341 |
| 385 | REQUESTER | stream_progress | 28500.0 |  | OBSERVED | 342 |
| 386 | REQUESTER | stream_progress | 28547.0 |  | OBSERVED | 343 |
| 387 | JOURNAL | journal_write_started | 28578.0 |  | OBSERVED |  |
| 388 | JOURNAL | journal_write_completed | 28594.0 |  | COMPLETED |  |
| 389 | REQUESTER | stream_progress | 28594.0 |  | OBSERVED | 344 |
| 390 | REQUESTER | stream_progress | 28625.0 |  | OBSERVED | 345 |
| 391 | REQUESTER | stream_progress | 28656.0 |  | OBSERVED | 346 |
| 392 | REQUESTER | stream_progress | 28703.0 |  | OBSERVED | 347 |
| 393 | REQUESTER | stream_progress | 28734.0 |  | OBSERVED | 348 |
| 394 | REQUESTER | stream_progress | 28781.0 |  | OBSERVED | 349 |
| 395 | REQUESTER | stream_progress | 28828.0 |  | OBSERVED | 350 |
| 396 | REQUESTER | stream_progress | 28859.0 |  | OBSERVED | 351 |
| 397 | REQUESTER | stream_progress | 28906.0 |  | OBSERVED | 352 |
| 398 | REQUESTER | stream_progress | 28938.0 |  | OBSERVED | 353 |
| 399 | REQUESTER | stream_progress | 28984.0 |  | OBSERVED | 354 |
| 400 | REQUESTER | stream_progress | 29016.0 |  | OBSERVED | 355 |
| 401 | REQUESTER | stream_progress | 29063.0 |  | OBSERVED | 356 |
| 402 | REQUESTER | stream_progress | 29094.0 |  | OBSERVED | 357 |
| 403 | REQUESTER | stream_progress | 29141.0 |  | OBSERVED | 358 |
| 404 | REQUESTER | stream_progress | 29172.0 |  | OBSERVED | 359 |
| 405 | REQUESTER | stream_progress | 29219.0 |  | OBSERVED | 360 |
| 406 | REQUESTER | stream_progress | 29297.0 |  | OBSERVED | 361 |
| 407 | REQUESTER | stream_progress | 29344.0 |  | OBSERVED | 362 |
| 408 | REQUESTER | stream_progress | 29375.0 |  | OBSERVED | 363 |
| 409 | REQUESTER | stream_progress | 29422.0 |  | OBSERVED | 364 |
| 410 | REQUESTER | stream_progress | 29469.0 |  | OBSERVED | 365 |
| 411 | REQUESTER | stream_progress | 29500.0 |  | OBSERVED | 366 |
| 412 | REQUESTER | stream_progress | 29547.0 |  | OBSERVED | 367 |
| 413 | REQUESTER | stream_progress | 29578.0 |  | OBSERVED | 368 |
| 414 | REQUESTER | stream_progress | 29625.0 |  | OBSERVED | 369 |
| 415 | REQUESTER | stream_progress | 29672.0 |  | OBSERVED | 370 |
| 416 | REQUESTER | stream_progress | 29703.0 |  | OBSERVED | 371 |
| 417 | REQUESTER | stream_progress | 29750.0 |  | OBSERVED | 372 |
| 418 | REQUESTER | stream_progress | 29781.0 |  | OBSERVED | 373 |
| 419 | REQUESTER | stream_progress | 29906.0 |  | OBSERVED | 374 |
| 420 | REQUESTER | stream_progress | 30031.0 |  | OBSERVED | 375 |
| 421 | PLANNING | heartbeat | 30078.0 |  | RUNNING | 375 |
| 422 | REQUESTER | stream_progress | 30141.0 |  | OBSERVED | 376 |
| 423 | REQUESTER | stream_progress | 30188.0 |  | OBSERVED | 377 |
| 424 | REQUESTER | stream_progress | 30219.0 |  | OBSERVED | 378 |
| 425 | REQUESTER | stream_progress | 30266.0 |  | OBSERVED | 379 |
| 426 | REQUESTER | stream_progress | 30391.0 |  | OBSERVED | 380 |
| 427 | REQUESTER | stream_progress | 30422.0 |  | OBSERVED | 381 |
| 428 | REQUESTER | stream_progress | 30469.0 |  | OBSERVED | 382 |
| 429 | REQUESTER | stream_progress | 30500.0 |  | OBSERVED | 383 |
| 430 | REQUESTER | stream_progress | 30547.0 |  | OBSERVED | 384 |
| 431 | JOURNAL | journal_write_started | 30672.0 |  | OBSERVED |  |
| 432 | JOURNAL | journal_write_completed | 30688.0 |  | COMPLETED |  |
| 433 | REQUESTER | stream_progress | 30688.0 |  | OBSERVED | 385 |
| 434 | REQUESTER | stream_progress | 30703.0 |  | OBSERVED | 386 |
| 435 | REQUESTER | stream_progress | 30750.0 |  | OBSERVED | 387 |
| 436 | REQUESTER | stream_progress | 30781.0 |  | OBSERVED | 388 |
| 437 | REQUESTER | stream_progress | 30828.0 |  | OBSERVED | 389 |
| 438 | REQUESTER | stream_progress | 30953.0 |  | OBSERVED | 390 |
| 439 | REQUESTER | stream_progress | 31078.0 |  | OBSERVED | 391 |
| 440 | REQUESTER | stream_progress | 31125.0 |  | OBSERVED | 392 |
| 441 | REQUESTER | stream_progress | 31172.0 |  | OBSERVED | 393 |
| 442 | REQUESTER | stream_progress | 31203.0 |  | OBSERVED | 394 |
| 443 | REQUESTER | stream_progress | 31250.0 |  | OBSERVED | 395 |
| 444 | REQUESTER | stream_progress | 31359.0 |  | OBSERVED | 396 |
| 445 | REQUESTER | stream_progress | 31406.0 |  | OBSERVED | 397 |
| 446 | REQUESTER | stream_progress | 31438.0 |  | OBSERVED | 398 |
| 447 | REQUESTER | stream_progress | 31484.0 |  | OBSERVED | 399 |
| 448 | REQUESTER | stream_progress | 31516.0 |  | OBSERVED | 400 |
| 449 | REQUESTER | stream_progress | 31641.0 |  | OBSERVED | 401 |
| 450 | REQUESTER | stream_progress | 31688.0 |  | OBSERVED | 402 |
| 451 | REQUESTER | stream_progress | 31719.0 |  | OBSERVED | 403 |
| 452 | REQUESTER | stream_progress | 31766.0 |  | OBSERVED | 404 |
| 453 | REQUESTER | stream_progress | 31797.0 |  | OBSERVED | 405 |
| 454 | REQUESTER | stream_progress | 31844.0 |  | OBSERVED | 406 |
| 455 | REQUESTER | stream_progress | 31875.0 |  | OBSERVED | 407 |
| 456 | REQUESTER | stream_progress | 31922.0 |  | OBSERVED | 408 |
| 457 | REQUESTER | stream_progress | 31953.0 |  | OBSERVED | 409 |
| 458 | REQUESTER | stream_progress | 32000.0 |  | OBSERVED | 410 |
| 459 | REQUESTER | stream_progress | 32047.0 |  | OBSERVED | 411 |
| 460 | REQUESTER | stream_progress | 32078.0 |  | OBSERVED | 412 |
| 461 | REQUESTER | stream_progress | 32125.0 |  | OBSERVED | 413 |
| 462 | REQUESTER | stream_progress | 32234.0 |  | OBSERVED | 414 |
| 463 | REQUESTER | stream_progress | 32359.0 |  | OBSERVED | 415 |
| 464 | REQUESTER | stream_progress | 32391.0 |  | OBSERVED | 416 |
| 465 | REQUESTER | stream_progress | 32438.0 |  | OBSERVED | 417 |
| 466 | REQUESTER | stream_progress | 32469.0 |  | OBSERVED | 418 |
| 467 | REQUESTER | stream_progress | 32516.0 |  | OBSERVED | 419 |
| 468 | REQUESTER | stream_progress | 32641.0 |  | OBSERVED | 420 |
| 469 | JOURNAL | journal_write_started | 32672.0 |  | OBSERVED |  |
| 470 | JOURNAL | journal_write_completed | 32688.0 |  | COMPLETED |  |
| 471 | REQUESTER | stream_progress | 32688.0 |  | OBSERVED | 421 |
| 472 | REQUESTER | stream_progress | 32719.0 |  | OBSERVED | 422 |
| 473 | REQUESTER | stream_progress | 32750.0 |  | OBSERVED | 423 |
| 474 | REQUESTER | stream_progress | 32875.0 |  | OBSERVED | 424 |
| 475 | REQUESTER | stream_progress | 32922.0 |  | OBSERVED | 425 |
| 476 | REQUESTER | stream_progress | 32969.0 |  | OBSERVED | 426 |
| 477 | REQUESTER | stream_progress | 33000.0 |  | OBSERVED | 427 |
| 478 | REQUESTER | stream_progress | 33125.0 |  | OBSERVED | 428 |
| 479 | REQUESTER | stream_progress | 33250.0 |  | OBSERVED | 429 |
| 480 | REQUESTER | stream_progress | 33281.0 |  | OBSERVED | 430 |
| 481 | REQUESTER | stream_progress | 33328.0 |  | OBSERVED | 431 |
| 482 | REQUESTER | stream_progress | 33359.0 |  | OBSERVED | 432 |
| 483 | REQUESTER | stream_progress | 33406.0 |  | OBSERVED | 433 |
| 484 | REQUESTER | stream_progress | 33516.0 |  | OBSERVED | 434 |
| 485 | REQUESTER | stream_progress | 33563.0 |  | OBSERVED | 435 |
| 486 | REQUESTER | stream_progress | 33594.0 |  | OBSERVED | 436 |
| 487 | REQUESTER | stream_progress | 33641.0 |  | OBSERVED | 437 |
| 488 | REQUESTER | stream_progress | 33688.0 |  | OBSERVED | 438 |
| 489 | REQUESTER | stream_progress | 33719.0 |  | OBSERVED | 439 |
| 490 | REQUESTER | stream_progress | 33766.0 |  | OBSERVED | 440 |
| 491 | REQUESTER | stream_progress | 33891.0 |  | OBSERVED | 441 |
| 492 | REQUESTER | stream_progress | 34000.0 |  | OBSERVED | 442 |
| 493 | REQUESTER | stream_progress | 34047.0 |  | OBSERVED | 443 |
| 494 | REQUESTER | stream_progress | 34078.0 |  | OBSERVED | 444 |
| 495 | REQUESTER | stream_progress | 34125.0 |  | OBSERVED | 445 |
| 496 | REQUESTER | stream_progress | 34156.0 |  | OBSERVED | 446 |
| 497 | REQUESTER | stream_progress | 34281.0 |  | OBSERVED | 447 |
| 498 | REQUESTER | stream_progress | 34313.0 |  | OBSERVED | 448 |
| 499 | REQUESTER | stream_progress | 34359.0 |  | OBSERVED | 449 |
| 500 | REQUESTER | stream_progress | 34391.0 |  | OBSERVED | 450 |
| 501 | REQUESTER | stream_progress | 34516.0 |  | OBSERVED | 451 |
| 502 | REQUESTER | stream_progress | 34563.0 |  | OBSERVED | 452 |
| 503 | REQUESTER | stream_progress | 34594.0 |  | OBSERVED | 453 |
| 504 | REQUESTER | stream_progress | 34641.0 |  | OBSERVED | 454 |
| 505 | JOURNAL | journal_write_started | 34672.0 |  | OBSERVED |  |
| 506 | JOURNAL | journal_write_completed | 34688.0 |  | COMPLETED |  |
| 507 | REQUESTER | stream_progress | 34688.0 |  | OBSERVED | 455 |
| 508 | REQUESTER | stream_progress | 34797.0 |  | OBSERVED | 456 |
| 509 | REQUESTER | stream_progress | 34844.0 |  | OBSERVED | 457 |
| 510 | REQUESTER | stream_progress | 34875.0 |  | OBSERVED | 458 |
| 511 | REQUESTER | stream_progress | 34922.0 |  | OBSERVED | 459 |
| 512 | REQUESTER | stream_progress | 34953.0 |  | OBSERVED | 460 |
| 513 | REQUESTER | stream_progress | 35000.0 |  | OBSERVED | 461 |
| 514 | REQUESTER | stream_progress | 35047.0 |  | OBSERVED | 462 |
| 515 | REQUESTER | stream_progress | 35078.0 |  | OBSERVED | 463 |
| 516 | PLANNING | heartbeat | 35078.0 |  | RUNNING | 463 |
| 517 | REQUESTER | stream_progress | 35125.0 |  | OBSERVED | 464 |
| 518 | REQUESTER | stream_progress | 35156.0 |  | OBSERVED | 465 |
| 519 | REQUESTER | stream_progress | 35203.0 |  | OBSERVED | 466 |
| 520 | REQUESTER | stream_progress | 35234.0 |  | OBSERVED | 467 |
| 521 | REQUESTER | stream_progress | 35281.0 |  | OBSERVED | 468 |
| 522 | REQUESTER | stream_progress | 35313.0 |  | OBSERVED | 469 |
| 523 | REQUESTER | stream_progress | 35359.0 |  | OBSERVED | 470 |
| 524 | REQUESTER | stream_progress | 35391.0 |  | OBSERVED | 471 |
| 525 | REQUESTER | stream_progress | 35438.0 |  | OBSERVED | 472 |
| 526 | REQUESTER | stream_progress | 35484.0 |  | OBSERVED | 473 |
| 527 | REQUESTER | stream_progress | 35516.0 |  | OBSERVED | 474 |
| 528 | REQUESTER | stream_progress | 35563.0 |  | OBSERVED | 475 |
| 529 | REQUESTER | stream_progress | 35594.0 |  | OBSERVED | 476 |
| 530 | REQUESTER | stream_progress | 35641.0 |  | OBSERVED | 477 |
| 531 | REQUESTER | stream_progress | 35688.0 |  | OBSERVED | 478 |
| 532 | REQUESTER | stream_progress | 35719.0 |  | OBSERVED | 479 |
| 533 | REQUESTER | stream_progress | 35766.0 |  | OBSERVED | 480 |
| 534 | REQUESTER | stream_progress | 35797.0 |  | OBSERVED | 481 |
| 535 | REQUESTER | stream_progress | 35844.0 |  | OBSERVED | 482 |
| 536 | REQUESTER | stream_progress | 35875.0 |  | OBSERVED | 483 |
| 537 | REQUESTER | stream_progress | 35922.0 |  | OBSERVED | 484 |
| 538 | REQUESTER | stream_progress | 35969.0 |  | OBSERVED | 485 |
| 539 | REQUESTER | stream_progress | 36000.0 |  | OBSERVED | 486 |
| 540 | REQUESTER | stream_progress | 36047.0 |  | OBSERVED | 487 |
| 541 | REQUESTER | stream_progress | 36078.0 |  | OBSERVED | 488 |
| 542 | REQUESTER | stream_progress | 36125.0 |  | OBSERVED | 489 |
| 543 | REQUESTER | stream_progress | 36172.0 |  | OBSERVED | 490 |
| 544 | REQUESTER | stream_progress | 36203.0 |  | OBSERVED | 491 |
| 545 | REQUESTER | stream_progress | 36250.0 |  | OBSERVED | 492 |
| 546 | REQUESTER | stream_progress | 36281.0 |  | OBSERVED | 493 |
| 547 | REQUESTER | stream_progress | 36328.0 |  | OBSERVED | 494 |
| 548 | REQUESTER | stream_progress | 36359.0 |  | OBSERVED | 495 |
| 549 | REQUESTER | stream_progress | 36406.0 |  | OBSERVED | 496 |
| 550 | REQUESTER | stream_progress | 36438.0 |  | OBSERVED | 497 |
| 551 | REQUESTER | stream_progress | 36484.0 |  | OBSERVED | 498 |
| 552 | REQUESTER | stream_progress | 36516.0 |  | OBSERVED | 499 |
| 553 | REQUESTER | stream_progress | 36563.0 |  | OBSERVED | 500 |
| 554 | REQUESTER | stream_progress | 36609.0 |  | OBSERVED | 501 |
| 555 | REQUESTER | stream_progress | 36641.0 |  | OBSERVED | 502 |
| 556 | JOURNAL | journal_write_started | 36688.0 |  | OBSERVED |  |
| 557 | JOURNAL | journal_write_completed | 36688.0 |  | COMPLETED |  |
| 558 | REQUESTER | stream_progress | 36703.0 |  | OBSERVED | 503 |
| 559 | REQUESTER | stream_progress | 36719.0 |  | OBSERVED | 504 |
| 560 | REQUESTER | stream_progress | 36766.0 |  | OBSERVED | 505 |
| 561 | REQUESTER | stream_progress | 36813.0 |  | OBSERVED | 506 |
| 562 | REQUESTER | stream_progress | 36844.0 |  | OBSERVED | 507 |
| 563 | REQUESTER | stream_progress | 36891.0 |  | OBSERVED | 508 |
| 564 | REQUESTER | stream_progress | 36922.0 |  | OBSERVED | 509 |
| 565 | REQUESTER | stream_progress | 36969.0 |  | OBSERVED | 510 |
| 566 | REQUESTER | stream_progress | 37000.0 |  | OBSERVED | 511 |
| 567 | REQUESTER | stream_progress | 37047.0 |  | OBSERVED | 512 |
| 568 | REQUESTER | stream_progress | 37078.0 |  | OBSERVED | 513 |
| 569 | REQUESTER | stream_progress | 37125.0 |  | OBSERVED | 514 |
| 570 | REQUESTER | first_valid_json_object | 37203.0 |  | OBSERVED |  |
| 571 | REQUESTER | stream_progress | 37203.0 |  | OBSERVED | 515 |
| 572 | REQUESTER | stream_completed | 37250.0 |  | COMPLETED |  |
| 573 | REQUESTER | requester_completed | 37266.0 |  | COMPLETED |  |
| 574 | REQUESTER | requester_parse_started | 37266.0 |  | OBSERVED |  |
| 575 | PLAN | plan_decode_started | 37266.0 |  | OBSERVED |  |
| 576 | PLAN | plan_schema_validation_started | 37266.0 |  | OBSERVED |  |
| 577 | VALIDATION | structural_validation_started | 37266.0 |  | OBSERVED |  |
| 578 | VALIDATION | security_validation_started | 37266.0 |  | OBSERVED |  |
| 579 | VALIDATION | semantic_validation_started | 37266.0 |  | OBSERVED |  |
| 580 | VALIDATION | integrity_validation_started | 37266.0 |  | OBSERVED |  |
| 581 | VALIDATION | component_validation_started | 37266.0 |  | OBSERVED |  |
| 582 | VALIDATION | persistence_contract_validation_started | 37266.0 |  | OBSERVED |  |
| 583 | VALIDATION | entrypoint_validation_started | 37266.0 |  | OBSERVED |  |
| 584 | VALIDATION | preview_contract_validation_started | 37266.0 |  | OBSERVED |  |
| 585 | REQUESTER | requester_parse_completed | 37266.0 |  | FAILED |  |
| 586 | PLAN | plan_schema_validation_completed | 37266.0 |  | FAILED |  |
| 587 | VALIDATION | structural_validation_completed | 37266.0 |  | FAILED |  |
| 588 | VALIDATION | security_validation_completed | 37266.0 |  | FAILED |  |
| 589 | VALIDATION | semantic_validation_completed | 37266.0 |  | FAILED |  |
| 590 | VALIDATION | integrity_validation_completed | 37266.0 |  | FAILED |  |
| 591 | VALIDATION | component_validation_completed | 37266.0 |  | FAILED |  |
| 592 | VALIDATION | persistence_contract_validation_completed | 37266.0 |  | FAILED |  |
| 593 | VALIDATION | entrypoint_validation_completed | 37266.0 |  | FAILED |  |
| 594 | VALIDATION | preview_contract_validation_completed | 37266.0 |  | FAILED |  |
| 595 | FOCAL_CORRECTION | focal_correction_started | 37266.0 |  | OBSERVED |  |
| 596 | FOCAL_CORRECTION | correction_prompt_built | 37266.0 |  | OBSERVED |  |
| 597 | FOCAL_CORRECTION | correction_request_started | 37266.0 |  | OBSERVED |  |
| 598 | REQUESTER | requester_started | 37266.0 |  | OBSERVED |  |
| 599 | JOURNAL | journal_write_started | 37266.0 |  | OBSERVED |  |
| 600 | JOURNAL | journal_write_completed | 37266.0 |  | COMPLETED |  |
| 601 | REQUESTER | readiness_check_started | 37281.0 |  | OBSERVED |  |
| 602 | JOURNAL | journal_write_started | 37281.0 |  | OBSERVED |  |
| 603 | JOURNAL | journal_write_completed | 37281.0 |  | COMPLETED |  |
| 604 | JOURNAL | journal_write_started | 37484.0 |  | OBSERVED |  |
| 605 | JOURNAL | journal_write_completed | 37484.0 |  | COMPLETED |  |
| 606 | REQUESTER | readiness_check_completed | 37484.0 |  | COMPLETED |  |
| 607 | REQUESTER | model_attempt_started | 37484.0 |  | OBSERVED |  |
| 608 | REQUESTER | http_request_started | 37625.0 |  | OBSERVED |  |
| 609 | PLANNING | heartbeat | 40094.0 |  | RUNNING | 515 |
| 610 | REQUESTER | response_headers_received | 40094.0 |  | COMPLETED |  |
| 611 | JOURNAL | journal_write_started | 40094.0 |  | OBSERVED |  |
| 612 | JOURNAL | journal_write_completed | 40109.0 |  | COMPLETED |  |
| 613 | REQUESTER | first_response_byte | 40109.0 |  | OBSERVED |  |
| 614 | REQUESTER | first_http_chunk | 40109.0 |  | OBSERVED |  |
| 615 | REQUESTER | first_nonempty_content | 40109.0 |  | OBSERVED |  |
| 616 | REQUESTER | stream_progress | 40109.0 |  | OBSERVED | 516 |
| 617 | REQUESTER | stream_progress | 40219.0 |  | OBSERVED | 517 |
| 618 | REQUESTER | stream_progress | 40266.0 |  | OBSERVED | 518 |
| 619 | REQUESTER | stream_progress | 40313.0 |  | OBSERVED | 519 |
| 620 | REQUESTER | stream_progress | 40344.0 |  | OBSERVED | 520 |
| 621 | REQUESTER | stream_progress | 40391.0 |  | OBSERVED | 521 |
| 622 | REQUESTER | stream_progress | 40500.0 |  | OBSERVED | 522 |
| 623 | REQUESTER | stream_progress | 40547.0 |  | OBSERVED | 523 |
| 624 | REQUESTER | stream_progress | 40578.0 |  | OBSERVED | 524 |
| 625 | REQUESTER | stream_progress | 40625.0 |  | OBSERVED | 525 |
| 626 | REQUESTER | stream_progress | 40656.0 |  | OBSERVED | 526 |
| 627 | REQUESTER | stream_progress | 40781.0 |  | OBSERVED | 527 |
| 628 | REQUESTER | stream_progress | 40813.0 |  | OBSERVED | 528 |
| 629 | REQUESTER | stream_progress | 40859.0 |  | OBSERVED | 529 |
| 630 | REQUESTER | stream_progress | 40891.0 |  | OBSERVED | 530 |
| 631 | REQUESTER | stream_progress | 40922.0 |  | OBSERVED | 531 |
| 632 | REQUESTER | stream_progress | 40969.0 |  | OBSERVED | 532 |
| 633 | REQUESTER | stream_progress | 41000.0 |  | OBSERVED | 533 |
| 634 | REQUESTER | stream_progress | 41047.0 |  | OBSERVED | 534 |
| 635 | REQUESTER | stream_progress | 41094.0 |  | OBSERVED | 535 |
| 636 | REQUESTER | stream_progress | 41125.0 |  | OBSERVED | 536 |
| 637 | REQUESTER | stream_progress | 41172.0 |  | OBSERVED | 537 |
| 638 | REQUESTER | stream_progress | 41219.0 |  | OBSERVED | 538 |
| 639 | REQUESTER | stream_progress | 41266.0 |  | OBSERVED | 539 |
| 640 | REQUESTER | stream_progress | 41391.0 |  | OBSERVED | 540 |
| 641 | REQUESTER | stream_progress | 41422.0 |  | OBSERVED | 541 |
| 642 | REQUESTER | stream_progress | 41469.0 |  | OBSERVED | 542 |
| 643 | REQUESTER | stream_progress | 41516.0 |  | OBSERVED | 543 |
| 644 | REQUESTER | stream_progress | 41547.0 |  | OBSERVED | 544 |
| 645 | REQUESTER | stream_progress | 41594.0 |  | OBSERVED | 545 |
| 646 | REQUESTER | stream_progress | 41625.0 |  | OBSERVED | 546 |
| 647 | REQUESTER | stream_progress | 41672.0 |  | OBSERVED | 547 |
| 648 | REQUESTER | stream_progress | 41719.0 |  | OBSERVED | 548 |
| 649 | REQUESTER | stream_progress | 41766.0 |  | OBSERVED | 549 |
| 650 | REQUESTER | stream_progress | 41797.0 |  | OBSERVED | 550 |
| 651 | REQUESTER | stream_progress | 41844.0 |  | OBSERVED | 551 |
| 652 | REQUESTER | stream_progress | 41875.0 |  | OBSERVED | 552 |
| 653 | REQUESTER | stream_progress | 42016.0 |  | OBSERVED | 553 |
| 654 | REQUESTER | stream_progress | 42047.0 |  | OBSERVED | 554 |
| 655 | JOURNAL | journal_write_started | 42094.0 |  | OBSERVED |  |
| 656 | JOURNAL | journal_write_completed | 42109.0 |  | COMPLETED |  |
| 657 | REQUESTER | stream_progress | 42109.0 |  | OBSERVED | 555 |
| 658 | REQUESTER | stream_progress | 42141.0 |  | OBSERVED | 556 |
| 659 | REQUESTER | stream_progress | 42172.0 |  | OBSERVED | 557 |
| 660 | REQUESTER | stream_progress | 42219.0 |  | OBSERVED | 558 |
| 661 | REQUESTER | stream_progress | 42266.0 |  | OBSERVED | 559 |
| 662 | REQUESTER | stream_progress | 42297.0 |  | OBSERVED | 560 |
| 663 | REQUESTER | stream_progress | 42344.0 |  | OBSERVED | 561 |
| 664 | REQUESTER | stream_progress | 42453.0 |  | OBSERVED | 562 |
| 665 | REQUESTER | stream_progress | 42516.0 |  | OBSERVED | 563 |
| 666 | REQUESTER | stream_progress | 42547.0 |  | OBSERVED | 564 |
| 667 | REQUESTER | stream_progress | 42594.0 |  | OBSERVED | 565 |
| 668 | REQUESTER | stream_progress | 42641.0 |  | OBSERVED | 566 |
| 669 | REQUESTER | stream_progress | 42688.0 |  | OBSERVED | 567 |
| 670 | REQUESTER | stream_progress | 42719.0 |  | OBSERVED | 568 |
| 671 | REQUESTER | stream_progress | 42766.0 |  | OBSERVED | 569 |
| 672 | REQUESTER | stream_progress | 42875.0 |  | OBSERVED | 570 |
| 673 | REQUESTER | stream_progress | 42922.0 |  | OBSERVED | 571 |
| 674 | REQUESTER | stream_progress | 42953.0 |  | OBSERVED | 572 |
| 675 | REQUESTER | stream_progress | 43000.0 |  | OBSERVED | 573 |
| 676 | REQUESTER | stream_progress | 43047.0 |  | OBSERVED | 574 |
| 677 | REQUESTER | stream_progress | 43078.0 |  | OBSERVED | 575 |
| 678 | REQUESTER | stream_progress | 43125.0 |  | OBSERVED | 576 |
| 679 | REQUESTER | stream_progress | 43172.0 |  | OBSERVED | 577 |
| 680 | REQUESTER | stream_progress | 43281.0 |  | OBSERVED | 578 |
| 681 | REQUESTER | stream_progress | 43406.0 |  | OBSERVED | 579 |
| 682 | REQUESTER | stream_progress | 43453.0 |  | OBSERVED | 580 |
| 683 | REQUESTER | stream_progress | 43500.0 |  | OBSERVED | 581 |
| 684 | REQUESTER | stream_progress | 43547.0 |  | OBSERVED | 582 |
| 685 | REQUESTER | stream_progress | 43625.0 |  | OBSERVED | 583 |
| 686 | REQUESTER | stream_progress | 43656.0 |  | OBSERVED | 584 |
| 687 | REQUESTER | stream_progress | 43703.0 |  | OBSERVED | 585 |
| 688 | REQUESTER | stream_progress | 43766.0 |  | OBSERVED | 586 |
| 689 | REQUESTER | stream_progress | 43813.0 |  | OBSERVED | 587 |
| 690 | REQUESTER | stream_progress | 43859.0 |  | OBSERVED | 588 |
| 691 | REQUESTER | stream_progress | 43891.0 |  | OBSERVED | 589 |
| 692 | REQUESTER | stream_progress | 43938.0 |  | OBSERVED | 590 |
| 693 | REQUESTER | stream_progress | 43969.0 |  | OBSERVED | 591 |
| 694 | REQUESTER | stream_progress | 44016.0 |  | OBSERVED | 592 |
| 695 | REQUESTER | stream_progress | 44047.0 |  | OBSERVED | 593 |
| 696 | JOURNAL | journal_write_started | 44094.0 |  | OBSERVED |  |
| 697 | JOURNAL | journal_write_completed | 44109.0 |  | COMPLETED |  |
| 698 | REQUESTER | stream_progress | 44109.0 |  | OBSERVED | 594 |
| 699 | REQUESTER | stream_progress | 44141.0 |  | OBSERVED | 595 |
| 700 | REQUESTER | stream_progress | 44266.0 |  | OBSERVED | 596 |
| 701 | REQUESTER | stream_progress | 44313.0 |  | OBSERVED | 597 |
| 702 | REQUESTER | stream_progress | 44359.0 |  | OBSERVED | 598 |
| 703 | REQUESTER | stream_progress | 44391.0 |  | OBSERVED | 599 |
| 704 | REQUESTER | stream_progress | 44438.0 |  | OBSERVED | 600 |
| 705 | REQUESTER | stream_progress | 44563.0 |  | OBSERVED | 601 |
| 706 | REQUESTER | stream_progress | 44609.0 |  | OBSERVED | 602 |
| 707 | REQUESTER | stream_progress | 44641.0 |  | OBSERVED | 603 |
| 708 | REQUESTER | stream_progress | 44688.0 |  | OBSERVED | 604 |
| 709 | REQUESTER | stream_progress | 44734.0 |  | OBSERVED | 605 |
| 710 | REQUESTER | stream_progress | 44766.0 |  | OBSERVED | 606 |
| 711 | REQUESTER | stream_progress | 44813.0 |  | OBSERVED | 607 |
| 712 | REQUESTER | stream_progress | 44859.0 |  | OBSERVED | 608 |
| 713 | REQUESTER | stream_progress | 44984.0 |  | OBSERVED | 609 |
| 714 | REQUESTER | stream_progress | 45016.0 |  | OBSERVED | 610 |
| 715 | REQUESTER | stream_progress | 45063.0 |  | OBSERVED | 611 |
| 716 | PLANNING | heartbeat | 45094.0 |  | RUNNING | 611 |
| 717 | REQUESTER | stream_progress | 45109.0 |  | OBSERVED | 612 |
| 718 | REQUESTER | stream_progress | 45156.0 |  | OBSERVED | 613 |
| 719 | REQUESTER | stream_progress | 45281.0 |  | OBSERVED | 614 |
| 720 | REQUESTER | stream_progress | 45313.0 |  | OBSERVED | 615 |
| 721 | REQUESTER | stream_progress | 45375.0 |  | OBSERVED | 616 |
| 722 | REQUESTER | stream_progress | 45406.0 |  | OBSERVED | 617 |
| 723 | REQUESTER | stream_progress | 45453.0 |  | OBSERVED | 618 |
| 724 | REQUESTER | stream_progress | 45500.0 |  | OBSERVED | 619 |
| 725 | REQUESTER | stream_progress | 45625.0 |  | OBSERVED | 620 |
| 726 | REQUESTER | stream_progress | 45750.0 |  | OBSERVED | 621 |
| 727 | REQUESTER | stream_progress | 45875.0 |  | OBSERVED | 622 |
| 728 | REQUESTER | stream_progress | 45906.0 |  | OBSERVED | 623 |
| 729 | REQUESTER | stream_progress | 45953.0 |  | OBSERVED | 624 |
| 730 | REQUESTER | stream_progress | 46000.0 |  | OBSERVED | 625 |
| 731 | REQUESTER | stream_progress | 46047.0 |  | OBSERVED | 626 |
| 732 | JOURNAL | journal_write_started | 46125.0 |  | OBSERVED |  |
| 733 | JOURNAL | journal_write_completed | 46141.0 |  | COMPLETED |  |
| 734 | REQUESTER | first_valid_json_object | 46141.0 |  | OBSERVED |  |
| 735 | REQUESTER | stream_progress | 46141.0 |  | OBSERVED | 627 |
| 736 | REQUESTER | stream_completed | 46172.0 |  | COMPLETED |  |
| 737 | REQUESTER | requester_completed | 46172.0 |  | COMPLETED |  |
| 738 | FOCAL_CORRECTION | correction_response_received | 46172.0 |  | OBSERVED |  |
| 739 | FOCAL_CORRECTION | correction_effectiveness_started | 46172.0 |  | OBSERVED |  |
| 740 | FOCAL_CORRECTION | correction_effectiveness_completed | 46188.0 |  | FAILED |  |
| 741 | FOCAL_CORRECTION | focal_correction_completed | 46188.0 |  | FAILED |  |
| 742 | PLANNING | span_failed | 46188.0 | 46172.0 | FAILED |  |
| 743 | JOURNAL | journal_write_started | 46188.0 |  | OBSERVED |  |
| 744 | JOURNAL | journal_write_completed | 46203.0 |  | COMPLETED |  |
| 745 | EXECUTION | build_completed | 46203.0 |  | FAILED |  |

## Duracoes agregadas

| Fase | Operacao | Duracao ms | Estado |
|---|---|---:|---|
| PLANNING | planning | 46172.0 | FAILED |

## Gaps

| Evento anterior | Evento seguinte | Gap ms | Classificacao |
|---|---|---:|---|
| mission_execution_started | project_builder_dispatch_started | 0.0 | desconhecido |
| project_builder_dispatch_started | build_project_entered | 16.0 | desconhecido |
| build_project_entered | span_started | 0.0 | desconhecido |
| span_started | prompt_build_started | 0.0 | desconhecido |
| prompt_build_started | prompt_build_completed | 0.0 | desconhecido |
| prompt_build_completed | request_payload_built | 0.0 | modelo |
| request_payload_built | requester_started | 0.0 | modelo |
| requester_started | journal_write_started | 0.0 | modelo |
| journal_write_started | journal_write_completed | 0.0 | I/O |
| journal_write_completed | readiness_check_started | 15.0 | modelo |
| readiness_check_started | journal_write_started | 0.0 | I/O |
| journal_write_started | journal_write_completed | 0.0 | I/O |
| journal_write_completed | journal_write_started | 172.0 | I/O |
| journal_write_started | journal_write_completed | 16.0 | I/O |
| journal_write_completed | readiness_check_completed | 0.0 | modelo |
| readiness_check_completed | model_attempt_started | 0.0 | modelo |
| model_attempt_started | http_request_started | 140.0 | modelo |
| http_request_started | heartbeat | 4657.0 | modelo |
| heartbeat | heartbeat | 5000.0 | sem progresso |
| heartbeat | response_headers_received | 2406.0 | modelo |
| response_headers_received | journal_write_started | 0.0 | I/O |
| journal_write_started | journal_write_completed | 16.0 | I/O |
| journal_write_completed | first_response_byte | 0.0 | modelo |
| first_response_byte | first_http_chunk | 0.0 | modelo |
| first_http_chunk | first_nonempty_content | 0.0 | modelo |
| first_nonempty_content | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 110.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 110.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | journal_write_started | 110.0 | modelo |
| journal_write_started | journal_write_completed | 15.0 | I/O |
| journal_write_completed | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 110.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | heartbeat | 31.0 | modelo |
| heartbeat | stream_progress | 16.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 78.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 78.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | journal_write_started | 78.0 | modelo |
| journal_write_started | journal_write_completed | 16.0 | I/O |
| journal_write_completed | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | journal_write_started | 47.0 | modelo |
| journal_write_started | journal_write_completed | 0.0 | I/O |
| journal_write_completed | stream_progress | 16.0 | modelo |
| stream_progress | stream_progress | 62.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 78.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 79.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 78.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 94.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | heartbeat | 0.0 | modelo |
| heartbeat | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 78.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | journal_write_started | 79.0 | modelo |
| journal_write_started | journal_write_completed | 15.0 | I/O |
| journal_write_completed | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 78.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 141.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | journal_write_started | 31.0 | modelo |
| journal_write_started | journal_write_completed | 16.0 | I/O |
| journal_write_completed | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | journal_write_started | 31.0 | modelo |
| journal_write_started | journal_write_completed | 16.0 | I/O |
| journal_write_completed | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 110.0 | modelo |
| stream_progress | heartbeat | 47.0 | modelo |
| heartbeat | stream_progress | 78.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | journal_write_started | 31.0 | modelo |
| journal_write_started | journal_write_completed | 16.0 | I/O |
| journal_write_completed | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 94.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 78.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 94.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 78.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | journal_write_started | 31.0 | modelo |
| journal_write_started | journal_write_completed | 16.0 | I/O |
| journal_write_completed | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 78.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | heartbeat | 47.0 | modelo |
| heartbeat | stream_progress | 63.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | journal_write_started | 125.0 | modelo |
| journal_write_started | journal_write_completed | 16.0 | I/O |
| journal_write_completed | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 15.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | journal_write_started | 31.0 | modelo |
| journal_write_started | journal_write_completed | 16.0 | I/O |
| journal_write_completed | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 110.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | journal_write_started | 31.0 | modelo |
| journal_write_started | journal_write_completed | 16.0 | I/O |
| journal_write_completed | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | heartbeat | 0.0 | modelo |
| heartbeat | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | journal_write_started | 47.0 | modelo |
| journal_write_started | journal_write_completed | 0.0 | I/O |
| journal_write_completed | stream_progress | 15.0 | modelo |
| stream_progress | stream_progress | 16.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | first_valid_json_object | 78.0 | modelo |
| first_valid_json_object | stream_progress | 0.0 | modelo |
| stream_progress | stream_completed | 47.0 | modelo |
| stream_completed | requester_completed | 16.0 | modelo |
| requester_completed | requester_parse_started | 0.0 | modelo |
| requester_parse_started | plan_decode_started | 0.0 | modelo |
| plan_decode_started | plan_schema_validation_started | 0.0 | desconhecido |
| plan_schema_validation_started | structural_validation_started | 0.0 | desconhecido |
| structural_validation_started | security_validation_started | 0.0 | desconhecido |
| security_validation_started | semantic_validation_started | 0.0 | desconhecido |
| semantic_validation_started | integrity_validation_started | 0.0 | desconhecido |
| integrity_validation_started | component_validation_started | 0.0 | desconhecido |
| component_validation_started | persistence_contract_validation_started | 0.0 | I/O |
| persistence_contract_validation_started | entrypoint_validation_started | 0.0 | I/O |
| entrypoint_validation_started | preview_contract_validation_started | 0.0 | desconhecido |
| preview_contract_validation_started | requester_parse_completed | 0.0 | modelo |
| requester_parse_completed | plan_schema_validation_completed | 0.0 | modelo |
| plan_schema_validation_completed | structural_validation_completed | 0.0 | desconhecido |
| structural_validation_completed | security_validation_completed | 0.0 | desconhecido |
| security_validation_completed | semantic_validation_completed | 0.0 | desconhecido |
| semantic_validation_completed | integrity_validation_completed | 0.0 | desconhecido |
| integrity_validation_completed | component_validation_completed | 0.0 | desconhecido |
| component_validation_completed | persistence_contract_validation_completed | 0.0 | I/O |
| persistence_contract_validation_completed | entrypoint_validation_completed | 0.0 | I/O |
| entrypoint_validation_completed | preview_contract_validation_completed | 0.0 | desconhecido |
| preview_contract_validation_completed | focal_correction_started | 0.0 | desconhecido |
| focal_correction_started | correction_prompt_built | 0.0 | desconhecido |
| correction_prompt_built | correction_request_started | 0.0 | modelo |
| correction_request_started | requester_started | 0.0 | modelo |
| requester_started | journal_write_started | 0.0 | modelo |
| journal_write_started | journal_write_completed | 0.0 | I/O |
| journal_write_completed | readiness_check_started | 15.0 | modelo |
| readiness_check_started | journal_write_started | 0.0 | I/O |
| journal_write_started | journal_write_completed | 0.0 | I/O |
| journal_write_completed | journal_write_started | 203.0 | I/O |
| journal_write_started | journal_write_completed | 0.0 | I/O |
| journal_write_completed | readiness_check_completed | 0.0 | modelo |
| readiness_check_completed | model_attempt_started | 0.0 | modelo |
| model_attempt_started | http_request_started | 141.0 | modelo |
| http_request_started | heartbeat | 2469.0 | modelo |
| heartbeat | response_headers_received | 0.0 | modelo |
| response_headers_received | journal_write_started | 0.0 | I/O |
| journal_write_started | journal_write_completed | 15.0 | I/O |
| journal_write_completed | first_response_byte | 0.0 | modelo |
| first_response_byte | first_http_chunk | 0.0 | modelo |
| first_http_chunk | first_nonempty_content | 0.0 | modelo |
| first_nonempty_content | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 110.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 141.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | journal_write_started | 47.0 | modelo |
| journal_write_started | journal_write_completed | 15.0 | I/O |
| journal_write_completed | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 63.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 109.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 78.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 63.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | journal_write_started | 47.0 | modelo |
| journal_write_started | journal_write_completed | 15.0 | I/O |
| journal_write_completed | stream_progress | 0.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 46.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | heartbeat | 31.0 | modelo |
| heartbeat | stream_progress | 15.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 32.0 | modelo |
| stream_progress | stream_progress | 62.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 125.0 | modelo |
| stream_progress | stream_progress | 31.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | stream_progress | 47.0 | modelo |
| stream_progress | journal_write_started | 78.0 | modelo |
| journal_write_started | journal_write_completed | 16.0 | I/O |
| journal_write_completed | first_valid_json_object | 0.0 | modelo |
| first_valid_json_object | stream_progress | 0.0 | modelo |
| stream_progress | stream_completed | 31.0 | modelo |
| stream_completed | requester_completed | 0.0 | modelo |
| requester_completed | correction_response_received | 0.0 | modelo |
| correction_response_received | correction_effectiveness_started | 0.0 | desconhecido |
| correction_effectiveness_started | correction_effectiveness_completed | 16.0 | desconhecido |
| correction_effectiveness_completed | focal_correction_completed | 0.0 | desconhecido |
| focal_correction_completed | span_failed | 0.0 | desconhecido |
| span_failed | journal_write_started | 0.0 | I/O |
| journal_write_started | journal_write_completed | 15.0 | I/O |
| journal_write_completed | build_completed | 0.0 | I/O |
