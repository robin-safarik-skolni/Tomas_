
import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.NoSuchElementException;
import java.util.Scanner;

public class Bible {
    public static void main(String[] args) throws FileNotFoundException {
        String jmenoSouboru = "Z:\\2026\\Programovani_repo\\bible\\Bible\\src\\complet.txt";
        File soubor = new File (jmenoSouboru);
        Scanner sc = null;
        try {
            sc = new Scanner(soubor);
        }catch(FileNotFoundException e){
            System.out.println("Soubor '" + jmenoSouboru + "' neexistuje!");
        }
        if(sc != null) {
            int pocitadlo = 0;
            while(true) {
                try {
                    String radek = sc.nextLine();
                    if (!radek.isBlank()) {
                        pocitadlo++;
                    }
                } catch (NoSuchElementException ex) {
                    break;
                }
            }
            System.out.println(pocitadlo);
        }
    }
}
