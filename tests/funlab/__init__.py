import unittest
from funlab.core.menu import MenuBar, MenuItem, Menu  # replace 'your_module' with the actual module name

class TestMenu(unittest.TestCase):
    def test_menu(self):
        mainmenu = MenuBar(title='', icon=f'/static/logo.svg')
        home = MenuItem(title='Home', icon="...")  # replace "..." with your SVG string
        ifmenu= Menu(title="Interface")
        if_cardmenu = Menu(title='Cards')
        if_cardmenu.append([MenuItem("Sample Card"), MenuItem("Card action"),MenuItem("Card Masonry")])
        ifmenu.append([MenuItem(title='Badges', badge='New'), if_cardmenu, MenuItem('Colors')])
        mainmenu.append([home, ifmenu])
        menus_test=Menu("M1").append([MenuItem("I11", f'/static/pig-money.svg')
                                        ,Menu('M12').append([MenuItem("I121"), MenuItem("I122")])
                                        , MenuItem("I13")
                                        , Menu('M14').append([MenuItem("I141"),
                                                            Menu("M142").append([MenuItem("M1421"), MenuItem("M1422")])
                                                            ])
                                    ]
                                    )
        menus_test2=Menu("M2").append([MenuItem("I21", '/static/pig-money.svg')
                                        ,Menu('M22', '/static/pig-money.svg').append([MenuItem("I221", '/static/pig-money.svg'), MenuItem("I222", '/static/pig-money.svg')])
                                        , MenuItem("I23", '/static/pig-money.svg')
                                        , Menu('M24', '/static/pig-money.svg').append([MenuItem("I241", '/static/pig-money.svg'),
                                                            Menu("M242", '/static/pig-money.svg').append([MenuItem("M2421", '/static/pig-money.svg'), MenuItem("M2422", '/static/pig-money.svg')])
                                                            ])
                                    ]
                                    )
        mainmenu.append([menus_test, menus_test2])
        layout='vertical'
        sidebar_html = mainmenu.html(layout)
        self.assertIsNotNone(sidebar_html)  # replace this with your actual assertion

if __name__ == '__main__':
    unittest.main()
