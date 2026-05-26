import java.io.File;
import java.io.FileNotFoundException;
import java.util.ArrayList;
import java.util.Scanner;

public class PrectiBibli {
    public static void main(String[] args) {
        String jmenoSouboru = "src\\complet.txt";
        File soubor = new File(jmenoSouboru);
        Scanner sc = null;
        String[] unikat = new String[5];
        int pocitadlo = 0;
        ArrayList arr = new ArrayList(); //vyroste tak, jak potřebujem

        try {
            sc = new Scanner(soubor);

            while (sc.hasNext()) {
                String slovo = sc.next();
                if(){
                    pocitadlo++;
                }
            }
        } catch (FileNotFoundException e) {
            System.out.println("Nenalezení.");
        }
        System.out.println(pocitadlo);
    }
}
