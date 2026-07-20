#include "lut.h"
#include <fstream>
int main()
{

  //lut::unit_test();
  //lut::lut12_10 l;

  //const unsigned short *ilut_data = l.ilut_data(); // inverse LUT in tabular form
  //const unsigned short *lut_data = l.lut_data();   // LUT in tabular form


  lut::lut_general<short,4096,1024,4> l;

  for (int i = 0; i < 4096; ++i)
  {
    float rel_error = (l.uncompress(l.compress(i))-i)/float(std::max(1,i));
    std::cout << i << ", " /*<< l.compress(i) << ", " */<< rel_error<<"" << std::endl;
  }


  std::ofstream lutfile("lut.txt");
  for (int i = 0; i < 4096; ++i)
    lutfile << l.compress(i)<<std::endl;
  std::ofstream ilutfile("ilut.txt");
  for (int i = 0; i < 1024; ++i)
    ilutfile << l.uncompress(i)<<std::endl;

}