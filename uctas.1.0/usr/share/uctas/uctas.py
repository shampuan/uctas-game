#!/usr/bin/env python3

import sys
import random
import os
import json # Skor kaydı için gerekli
from datetime import datetime # Tarih ve saat bilgisi için
import pygame # ses çalmak için kullanacağız
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, 
                             QAction, QMessageBox)
from PyQt5.QtGui import QPixmap, QPainter, QFont, QColor, QIcon
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer

# Debian/Pardus grafik uyumluluğu
os.environ['QT_QPA_PLATFORM'] = 'xcb'

# --- AYARLAR VE KOORDİNATLAR --- burayı ful yapay zeka hazırladı
BOARD_W, BOARD_H = 404, 502
V_LINES = [57, 214, 359]
H_LINES = [100, 248, 401]
BOARD_POSITIONS = [QPoint(x, y) for y in H_LINES for x in V_LINES]

SIYAH_SPAWN = [QPoint(57, 460), QPoint(214, 460), QPoint(359, 460)]
BEYAZ_SPAWN = [QPoint(57, 40), QPoint(214, 40), QPoint(359, 40)]

ADJACENCY = {
    0: [1, 3], 1: [0, 2, 4], 2: [1, 5],
    3: [0, 4, 6], 4: [1, 3, 5, 7], 5: [2, 4, 8],
    6: [3, 7], 7: [4, 6, 8], 8: [5, 7]
}
WIN_COMBOS = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8)]

class UctasGame(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(BOARD_W, BOARD_H)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Skor dosyası yolu: ~/.config/uctas/skor.json
        self.config_dir = os.path.expanduser("~/.config/uctas")
        self.score_file = os.path.join(self.config_dir, "skor.json")
        self.ensure_config_dir()

        # Görseller - aynı dizinden çağırtıyorum.
        self.board_pix = QPixmap(os.path.join(self.base_dir, "uctastahta.png"))
        self.siyah_pix = [QPixmap(os.path.join(self.base_dir, f"siyah{i}.png")) for i in range(1, 4)]
        self.beyaz_pix = [QPixmap(os.path.join(self.base_dir, f"beyaz{i}.png")) for i in range(1, 4)]
        
        # PYGAME MIXER SES KURULUMU - ses seviyeleri böyle kalsın daha iyi
        pygame.mixer.init()
        pygame.mixer.music.load(os.path.join(self.base_dir, "okulbahcesi.mp3"))
        pygame.mixer.music.set_volume(0.5) # yüzde 50
        self.zil_sesi = pygame.mixer.Sound(os.path.join(self.base_dir, "okulzili.mp3"))
        self.zil_sesi.set_volume(0.2) # yüzde 20
        
        self.init_game()

    def ensure_config_dir(self):
        """Skor klasörünü kontrol eder, yoksa oluşturur."""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)

    def save_score(self, winner):
        """Kazananı ve zamanı JSON dosyasına alt alta ekler."""
        new_entry = {
            "kazanan": "Oyuncu" if winner == "siyah" else "Yapay Zeka",
            "tarih_saat": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        scores = []
        if os.path.exists(self.score_file):
            try:
                with open(self.score_file, "r", encoding="utf-8") as f:
                    scores = json.load(f)
            except:
                scores = []
        
        scores.append(new_entry)
        
        with open(self.score_file, "w", encoding="utf-8") as f:
            json.dump(scores, f, ensure_ascii=False, indent=4)

    def init_game(self):
        self.board = [None] * 9
        self.sira = "siyah"
        self.siyah_dis = [0, 1, 2]
        self.beyaz_dis = [0, 1, 2]
        self.siyah_konum = {}
        self.beyaz_konum = {}
        self.secili_idx = None
        self.oyun_bitti = False
        self.paused = False
        self.kazanan = None
        
        self.zil_sesi.stop()
        pygame.mixer.music.play(-1)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPixmap(0, 0, self.board_pix)
        
        font = QFont("Liberation Sans", 25)
        painter.setFont(font)

        for i in range(3):
            s_pos = SIYAH_SPAWN[i] if i in self.siyah_dis else BOARD_POSITIONS[self.siyah_konum[i]]
            self.draw_token(painter, self.siyah_pix[i], s_pos, self.secili_idx == self.siyah_konum.get(i) and i not in self.siyah_dis)
            b_pos = BEYAZ_SPAWN[i] if i in self.beyaz_dis else BOARD_POSITIONS[self.beyaz_konum[i]]
            self.draw_token(painter, self.beyaz_pix[i], b_pos)

        if self.oyun_bitti:
            painter.setPen(Qt.green if self.kazanan == "siyah" else Qt.red)
            txt = "OYUNCU KAZANDI!" if self.kazanan == "siyah" else "YZ KAZANDI!"
            painter.drawText(self.rect(), Qt.AlignTop | Qt.AlignHCenter, txt)

    def draw_token(self, painter, pix, pos, selected=False):
        rect = QRect(0, 0, 82, 82)
        rect.moveCenter(pos)
        if selected:
            painter.setPen(QColor(255, 200, 0))
            painter.drawEllipse(pos, 41, 41)
        painter.drawPixmap(rect, pix)

    def mousePressEvent(self, event):
        if self.oyun_bitti or self.paused or self.sira != "siyah": return
        idx = self.get_clicked_idx(event.pos())
        if idx is not None:
            if self.siyah_dis:
                if self.board[idx] is None:
                    tid = self.siyah_dis.pop(0)
                    self.siyah_konum[tid] = idx
                    self.board[idx] = "siyah"
                    self.finish_turn()
            else:
                if self.board[idx] == "siyah": self.secili_idx = idx
                elif self.secili_idx is not None and idx in ADJACENCY[self.secili_idx] and self.board[idx] is None:
                    self.move_token("siyah", self.secili_idx, idx)
                    self.secili_idx = None
                    self.finish_turn()
        self.update()

    def move_token(self, player, old_idx, new_idx):
        self.board[old_idx] = None
        self.board[new_idx] = player
        target_dict = self.siyah_konum if player == "siyah" else self.beyaz_konum
        for tid, bidx in target_dict.items():
            if bidx == old_idx:
                target_dict[tid] = new_idx
                break

    def get_clicked_idx(self, pos): 
        for i, p in enumerate(BOARD_POSITIONS):
            if (pos - p).manhattanLength() < 40: return i 
        return None

    def finish_turn(self):
        if self.check_win("siyah"):
            self.oyun_bitti = True
            self.kazanan = "siyah"
            self.save_score("siyah") # Skoru kaydet (diğerleri aşağılarda).
            self.oyun_sonu_sesi()
        else:
            self.sira = "beyaz"
            QTimer.singleShot(700, self.ai_move)
        self.update()

    def oyun_sonu_sesi(self):
        pygame.mixer.music.stop() 
        self.zil_sesi.play()      

    def check_win(self, p):
        return any(all(self.board[i] == p for i in c) for c in WIN_COMBOS)

    def ai_move(self):
        if self.oyun_bitti or self.paused: return
        if random.random() < 0.15: 
            self.make_random_move()
            return

        target_move = None
        moving_tid = None

        if self.beyaz_dis:
            target_move = self.find_best_move("beyaz")
            if target_move is None: target_move = self.find_best_move("siyah")
            if target_move is None:
                bos = [i for i, v in enumerate(self.board) if v is None]
                target_move = 4 if 4 in bos else random.choice(bos)
            tid = self.beyaz_dis.pop(0)
            self.beyaz_konum[tid] = target_move
            self.board[target_move] = "beyaz"
        else:
            for tid, bidx in self.beyaz_konum.items():
                for move in [h for h in ADJACENCY[bidx] if self.board[h] is None]:
                    self.board[bidx] = None
                    self.board[move] = "beyaz"
                    if self.check_win("beyaz"): target_move, moving_tid = move, tid
                    self.board[move] = None
                    self.board[bidx] = "beyaz"
                    if target_move is not None: break
                if target_move is not None: break

            if target_move is None:
                danger = self.find_best_move("siyah")
                if danger is not None:
                    for tid, bidx in self.beyaz_konum.items():
                        if danger in ADJACENCY[bidx] and self.board[danger] is None:
                            target_move, moving_tid = danger, tid
                            break

            if target_move is None:
                starts = [tid for tid, bidx in self.beyaz_konum.items() if any(self.board[h] is None for h in ADJACENCY[bidx])]
                if starts:
                    moving_tid = random.choice(starts)
                    target_move = random.choice([h for h in ADJACENCY[self.beyaz_konum[moving_tid]] if self.board[h] is None])

            if moving_tid is not None:
                self.move_token("beyaz", self.beyaz_konum[moving_tid], target_move)

        if self.check_win("beyaz"):
            self.oyun_bitti = True
            self.kazanan = "beyaz"
            self.save_score("beyaz") # Skoru kaydet
            self.oyun_sonu_sesi()
        else:
            self.sira = "siyah"
        self.update()

    def make_random_move(self):
        if self.beyaz_dis:
            bos = [i for i, v in enumerate(self.board) if v is None]
            target = random.choice(bos)
            tid = self.beyaz_dis.pop(0)
            self.beyaz_konum[tid] = target
            self.board[target] = "beyaz"
        else:
            starts = [tid for tid, bidx in self.beyaz_konum.items() if any(self.board[h] is None for h in ADJACENCY[bidx])]
            if starts:
                tid = random.choice(starts)
                target = random.choice([h for h in ADJACENCY[self.beyaz_konum[tid]] if self.board[h] is None])
                self.move_token("beyaz", self.beyaz_konum[tid], target)
        
        if self.check_win("beyaz"):
            self.oyun_bitti, self.kazanan = True, "beyaz"
            self.save_score("beyaz") # Skoru kaydet
            self.oyun_sonu_sesi()
        else:
            self.sira = "siyah"
        self.update()

    def find_best_move(self, p):
        for c in WIN_COMBOS:
            if sum(1 for i in c if self.board[i] == p) == 2 and sum(1 for i in c if self.board[i] is None) == 1:
                return [i for i in c if self.board[i] is None][0]
        return None

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Üçtaş")
        base = os.path.dirname(os.path.abspath(__file__))
        self.setWindowIcon(QIcon(os.path.join(base, "uctasico.png")))
        self.game_widget = UctasGame()
        self.setCentralWidget(self.game_widget)
        
        m = self.menuBar()
        g = m.addMenu("Oyun")
        new = QAction("Yeni Oyun", self); new.triggered.connect(self.game_widget.init_game); g.addAction(new)
        self.p_act = QAction("Duraklat", self); self.p_act.triggered.connect(self.toggle_p); g.addAction(self.p_act)
        
        # Skor tablosunu gösteren yeni menü öğesi
        score_act = QAction("Skor Tablosu", self)
        score_act.triggered.connect(self.show_scores)
        g.addAction(score_act)
        
        about = QAction("Hakkında", self); about.triggered.connect(self.show_a); g.addAction(about)

    def show_scores(self):
        """Kayıtlı skorları bir pencerede gösterir. Oyun ilk açıldığında mesaj göstertiyorum"""
        if not os.path.exists(self.game_widget.score_file):
            QMessageBox.information(self, "Skor Tablosu", "Henüz kaydedilmiş bir maç yok.")
            return
            
        try:
            with open(self.game_widget.score_file, "r", encoding="utf-8") as f:
                scores = json.load(f)
            
            # Son maçlar en üstte görünsün diye listeyi ters çeviriyoruz
            txt = "<b>Tüm Zamanların Skorları:</b><br><br>"
            for s in reversed(scores):
                txt += f"• {s['kazanan']} - {s['tarih_saat']}<br>"
            
            QMessageBox.about(self, "Skor Tablosu", txt)
        except:
            QMessageBox.warning(self, "Hata", "Skor dosyası okunamadı.")

    def toggle_p(self):
        self.game_widget.paused = not self.game_widget.paused
        if self.game_widget.paused: pygame.mixer.music.pause()
        else: pygame.mixer.music.unpause()
        self.p_act.setText("Devam Et" if self.game_widget.paused else "Duraklat")

    def show_a(self):
        msg = ("<b>Üç Taş Oyunu Hakkında</b><br><br>Sürüm: 1.0.0<br>Lisans: GNU GPLv3<br>UI: Python3 PyQt5<br>"
               "Geliştirici: A. Serhat KILIÇOĞLU (shampuan)<br>Github: <a href='http://www.github.com/shampuan'>www.github.com/shampuan</a><br><br>"
               "Eski günleri hatırlamak için yapılmış basit bir oyun.<br><br>Bu program hiçbir garanti getirmez.<br><br>Telif hakkı © 2026 - A. Serhat KILIÇOĞLU")
        QMessageBox.about(self, "Hakkında", msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Liberation Sans"))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
